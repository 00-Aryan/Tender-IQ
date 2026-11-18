"""Capture evidence from indexed PDFs; run from the repository root with
`uv run python -m tender_iq.evaluation.capture_evidence`.

This calls the RAG chain directly and bypasses HTTP handling. Execution may use
paid model APIs. Importing the module does not load models or send requests.
"""

import argparse  # Read options such as question IDs and upload mappings.
import hashlib  # Hash code, dataset and dependency lock files for provenance.
import json  # Read datasets and write portable result records.
import math  # Reject infinite or invalid pause durations.
import subprocess  # Read Git revision and branch information.
import time  # Measure durations with a monotonic clock.
from datetime import datetime  # Record human-readable run dates.
from pathlib import Path  # Build paths independently of shell separators.
from zoneinfo import ZoneInfo  # Keep timestamps in the user's timezone.

from tender_iq.evaluation.dataset import DATASET, EVALUATION_DIR, PROJECT_ROOT, load_dataset

RESULTS_DIR = EVALUATION_DIR / "captures"  # Raw evidence stays separate from scores.
TIMEZONE = ZoneInfo("Asia/Kolkata")  # Include the India-time offset in saved timestamps.


def timestamp():
    """Input: none. Output: current ISO timestamp, for run/case traceability."""
    return datetime.now(TIMEZONE).isoformat()  # Include date, time and UTC offset.


def get_git_provenance():
    """Input: none. Output: git commit SHA and branch name or fallback dictionary."""
    try:
        commit_sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, stderr=subprocess.DEVNULL, text=True
        ).strip()
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=PROJECT_ROOT, stderr=subprocess.DEVNULL, text=True
        ).strip()
        return {"commit_sha": commit_sha, "branch": branch}
    except Exception:
        return {"commit_sha": "unknown", "branch": "unknown"}


def get_environment_provenance(mapping, dataset_path=DATASET):
    """Input: upload mapping and dataset path. Output: comprehensive provenance dict.

    Records git commit, branch, dataset/document hashes, capture script hash, uv.lock hash,
    models, retrieval settings, and upload mappings without sensitive credentials.
    """
    git_info = get_git_provenance()
    uv_lock_path = PROJECT_ROOT / "uv.lock"
    uv_lock_sha = hashlib.sha256(uv_lock_path.read_bytes()).hexdigest() if uv_lock_path.exists() else None
    script_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()

    dataset_raw = dataset_path.read_bytes()
    dataset_data = json.loads(dataset_raw)
    dataset_sha = hashlib.sha256(dataset_raw).hexdigest()

    return {
        "git": git_info,
        "dataset": {
            "path": str(dataset_path.resolve()),
            "version": dataset_data["dataset_version"],
            "sha256": dataset_sha,
        },
        "documents": {
            tender_id: {
                "pdf_path": doc["pdf_path"],
                "sha256": doc["sha256"],
            }
            for tender_id, doc in dataset_data.get("documents", {}).items()
        },
        "capture_script_sha256": script_sha,
        "uv_lock_sha256": uv_lock_sha,
        "timezone": str(TIMEZONE),
        "upload_mappings": mapping,
        "models": {
            "generation": {
                "model": "gemini-3.1-flash-lite",
                "provider": "google_genai",
                "temperature": 0.0,
            },
            "embeddings": {
                "model": "all-MiniLM-L6-v2",
                "provider": "huggingface",
            },
        },
        "retrieval_settings": {
            "search_type": "mmr",
            "k": 6,
            "fetch_k": 20,
            "lambda_mult": 0.85,
            "ensemble_weights": [0.4, 0.6],  # [BM25, Vector]
            "query_expansion": {
                "enabled": True,
                "method": "llm_multi_query",
            },
        },
    }


def load_cases(dataset_path=DATASET, question_ids=None):
    """Input: one versioned dataset and optional IDs. Output: cases ready to capture.

    Read the shared reviewed dataset, resolve each case's PDF identity, and select
    each requested question once. Supplied passages and historical CSV labels are
    not part of this dataset.
    """
    dataset, digest = load_dataset(dataset_path)
    wanted = set(question_ids) if question_ids is not None else None
    if question_ids is not None and len(question_ids) != len(wanted):
        raise ValueError("Question IDs must be unique.")
    selected = []
    for case in dataset["cases"]:
        if wanted is not None and case["id"] not in wanted:
            continue
        selected.append({
            "dataset_path": str(dataset_path.resolve()),
            "dataset_sha256": digest,
            "dataset_version": dataset["dataset_version"],
            "case": case,
            "document_reference": {"tender": case["tender_id"], **dataset["documents"][case["tender_id"]]},
        })
    missing = (wanted or set()) - {item["case"]["id"] for item in selected}
    if missing or not selected:
        raise ValueError(f"Missing selected questions: {', '.join(sorted(missing))}")
    return selected


def document_mapping(selected, mappings, single_id=None):
    """Input: cases, TENDER=UPLOAD strings or one upload ID. Output: mapping dict.

    Require exactly one upload per selected tender before starting model calls.
    """
    result = {}  # Build tender ID to local upload ID associations.
    for mapping in mappings:  # Accept repeated --document-map options.
        tender, separator, document_id = mapping.partition("=")  # Split only the first equals sign.
        tender, document_id = tender.strip(), document_id.strip()  # Remove accidental surrounding spaces.
        if not separator or not tender or not document_id or tender in result:  # Reject ambiguous mapping input.
            raise ValueError("Use unique --document-map TENDER_ID=UPLOAD_ID entries.")
        result[tender] = document_id  # Associate this tender with its existing upload.
    tenders = {item["case"]["tender_id"] for item in selected}  # Determine required document identities.
    if single_id is not None:  # Preserve the simpler one-tender command.
        if result or len(tenders) != 1 or not single_id.strip():  # One ID cannot represent two tenders.
            raise ValueError("--document-id requires one tender and no --document-map.")
        result[next(iter(tenders))] = single_id.strip()  # Assign the only selected tender.
    if set(result) != tenders:  # Reject missing and unnecessary mappings.
        raise ValueError("Provide exactly one upload mapping for every selected tender.")
    return result  # Each selected case can now resolve its upload.


def failure_details(exc, stage):
    """Input: caught exception and current stage. Output: safe diagnostic dict.

    Keep class/module, numeric HTTP status and known pipeline frame names.
    Never store exception messages, request bodies, headers, URLs or credentials.
    Wrapped exceptions are inspected for a numeric provider status when available.
    """
    details = {  # Basic fields remain available for non-provider exceptions too.
        "type": type(exc).__name__,  # Identify the original failure category.
        "module": type(exc).__module__,  # Distinguish provider ServerError from another library's error.
        "stage": stage,  # Identify the outer operation that failed.
        "http_status": None,  # Unknown is preferable to guessing 500 or 503.
        "pipeline_frames": [],  # Retain only known function names, not raw tracebacks.
    }
    known_frames = {  # These names allow useful stage hints without exposing payloads.
        "expand_query", "retrieve_and_deduplicate", "answer_with_sources", "capture_case",
    }
    current, visited = exc, set()  # Follow exception wrappers safely without cycles.
    while current is not None and id(current) not in visited:  # Inspect every available cause once.
        visited.add(id(current))  # Prevent repeated traversal of a cyclic chain.
        for attribute in ("status_code", "code"):  # Libraries expose HTTP codes under different names.
            code = getattr(current, attribute, None)  # Do not read raw provider response bodies.
            if type(code) is int and 100 <= code <= 599 and details["http_status"] is None:  # Save only HTTP-like integers.
                details["http_status"] = code  # Make transient/auth/quota failures distinguishable later.
        trace = current.__traceback__  # Read frame identities without formatting traceback source lines.
        while trace is not None:  # Examine where the failure propagated.
            name = trace.tb_frame.f_code.co_name  # Function name contains no request data.
            if name in known_frames and name not in details["pipeline_frames"]:  # Restrict persisted names.
                details["pipeline_frames"].append(name)  # Preserve a compact diagnostic trail.
            trace = trace.tb_next  # Move toward the originating frame.
        current = current.__cause__ or current.__context__  # Inspect wrapped provider exceptions too.
    if "expand_query" in details["pipeline_frames"]:  # Expansion has its own invocation wrapper.
        details["stage"] = "query_expansion"  # Identify failure before final answer generation.
    elif "retrieve_and_deduplicate" in details["pipeline_frames"]:  # Retrieval errors use this wrapper.
        details["stage"] = "retrieval"  # Distinguish retrieval from answer-model work.
    # answer_with_sources alone is not proof that the final model call failed.
    return details  # Missing status/stage detail stays explicitly unknown or coarse.


def capture_case(case, document_id, progress=None):
    """Input: case, upload ID, optional mutable stage tracker. Output: captured result.

    Read an existing completed upload, retrieve actual chunks and invoke the chain
    with evidence enabled. Exceptions propagate to capture_batch for recording.
    """
    progress = progress if progress is not None else {}  # Share stage updates with the batch caller.
    progress["stage"] = "runtime_imports"  # Track initialization failures before any lookup.
    from tender_iq.crud.tenders import get_tender_by_id  # Reuse app document lookup semantics.
    from tender_iq.db.session import SessionLocal  # Reuse the app's SQLite connection configuration.
    from tender_iq.services.chat import get_all_chunks_for_tender  # Load the same BM25 corpus as chat.
    from tender_iq.rag.tender_rag import build_rag_chain  # Reuse generation rather than duplicate it.

    progress["stage"] = "database_lookup"  # Explain missing/unfinished/wrong-document failures.
    with SessionLocal() as db:  # Close the database session even when validation fails.
        tender = get_tender_by_id(db, document_id)  # Resolve JOB or bid/hash identity.
        if tender is None:  # No local upload matches this supplied identifier.
            raise ValueError("Upload ID was not found in the current local database.")
        if tender.status != "completed":  # Never evaluate partially ingested content deliberately.
            raise ValueError("Document ingestion must be completed first.")
        if tender.bid_id != case["tender_id"]:  # Check the uploaded tender matches the dataset question.
            raise ValueError("Uploaded tender identity does not match this question.")
        vector_id = tender.bid_id or tender.id  # Use the same Chroma identity as chat.
        specs = tender.specs  # Retain structured evidence supplied to the answer model.
        job_id = tender.id  # Record the upload record actually resolved.

    progress["stage"] = "chunk_loading"  # Model loading may occur inside vector-store setup here.
    timings = {}  # Collect existing pipeline stage measurements.
    started = time.perf_counter()  # Start monotonic timing for chunk loading.
    chunks = get_all_chunks_for_tender(vector_id)  # Read actual stored PDF chunks, never supplied passages.
    timings["chunk_loading_ms"] = round((time.perf_counter() - started) * 1000, 2)  # Store milliseconds.
    if not chunks:  # A database record alone does not establish indexed evidence exists.
        raise ValueError("No indexed chunks found for this document.")
    progress["stage"] = "chain_construction"  # Separate setup from invocation failures.
    chain = build_rag_chain(  # Construct the existing RAG pipeline with opt-in capture.
        tender_id=vector_id,  # Filter vector retrieval to this tender.
        chunk=chunks,  # Supply its corpus for BM25.
        tender_obj=specs,  # Supply the stored structured overview.
        stage_latencies_ms=timings,  # Preserve existing stage-timing instrumentation.
        capture_evidence=True,  # Explicitly enable full evidence only for this experiment.
    )
    progress["stage"] = "chain_invocation"  # Includes expansion, retrieval and answer generation.
    result = chain.invoke(case["question"])  # Make the actual generation calls, which may incur cost.
    progress["stage"] = "result_extraction"  # Identify failures to obtain required output fields.
    return {  # Exclude raw Document objects so output is JSON-ready.
        "resolved_job_id": job_id,  # Link output to the resolved upload.
        "vector_tender_id": vector_id,  # Record which index filter was used.
        "answer": result["answer"],  # Preserve the ungraded generated answer.
        "evaluation_evidence": result["evaluation_evidence"],  # Preserve complete model evidence.
        "latency_breakdown_ms": result["latency_breakdown_ms"],  # Preserve existing stage timings.
        "answer_call_tokens": result.get("tokens_used"),  # Answer-call usage only, not total pipeline tokens.
    }


def save_result(report, output=None):
    """Input: report and optional current-run path. Output: saved Path.

    Reserve new files exclusively; checkpoint this run through atomic replacement.
    Previous runs are never selected automatically for overwriting.
    """
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)  # Create the output directory when needed.
    destination = output or RESULTS_DIR / f"evidence_{report['run_id']}.json"  # Reuse only an explicit current-run path.
    temporary = destination.with_suffix(".json.tmp") if output else destination  # Stage checkpoint writes beside output.
    with temporary.open("x", encoding="utf-8") as file:  # Refuse accidental collisions with existing files.
        json.dump(report, file, indent=2, ensure_ascii=False)  # Preserve readable Unicode evidence.
        file.write("\n")  # End the JSON file with a standard newline.
    if output:  # Initial reservation already wrote directly to its new destination.
        temporary.replace(destination)  # Readers see a complete previous or updated checkpoint.
    return destination  # Tell the caller where the artifact was saved.


def capture_batch(selected, mapping, pause=2.0, max_consecutive_provider_failures=3):
    """Input: cases, upload mapping, pause and failure limit. Output: saved report dict.

    Attempt each case once at this runner level. Save failures and continue; SDK
    retries remain provider defaults. Stop after the configured consecutive provider
    failures; preserve unattempted IDs separately. Checkpoint without grading.
    """
    if type(max_consecutive_provider_failures) is not int or max_consecutive_provider_failures < 1:  # Require a usable stop threshold.
        raise ValueError("Provider failure limit must be a positive integer.")
    dataset_path = Path(selected[0]["dataset_path"]) if selected and "dataset_path" in selected[0] else DATASET
    provenance = get_environment_provenance(mapping, dataset_path=dataset_path)
    report = {  # Store run-level scope so results cannot be mistaken for HTTP evaluation.
        "run_id": datetime.now(TIMEZONE).strftime("%Y-%m-%d_%H-%M-%S-%f"),  # Readable unique filename component.
        "schema_version": 1,  # Match the consolidated capture format.
        "dataset_version": selected[0]["dataset_version"],  # Identify the question version.
        "dataset_sha256": selected[0]["dataset_sha256"],  # Pin the exact reference bytes.
        "started_at": timestamp(),  # Record the run's wall-clock start.
        "provenance": provenance,  # Full reproducible configuration without secrets.
        "execution_path": "Direct RAG chain; bypasses API validation, routing and response formatting.",  # State bypassed layers.
        "identity_limit": "Tender ID checked; indexed PDF bytes/version not independently verified.",  # Avoid overstating isolation.
        "timing_scope": "Local lookup, chunk loading, chain construction and invocation; not HTTP latency.",  # Define the clock boundary.
        "pause_seconds": pause,  # Record the requested gap between cases.
        "attempts_per_question": 1,  # Runner attempts, not a count of hidden SDK retries.
        "max_consecutive_provider_failures": max_consecutive_provider_failures,  # Record the stop policy.
        "stop_reason": None,  # Filled only if the failure streak stops this batch.
        "not_attempted_ids": [],  # Unexecuted cases must not be counted as failed attempts.
        "status": "running",  # An interrupted checkpoint must not look completed.
        "planned_cases": len(selected),  # Preserve the denominator before execution.
        "results": [],  # Accumulate both successful and failed case records.
    }
    output = save_result(report)  # Reserve an output file before potentially paid calls.
    started = time.perf_counter()  # Measure total execution independently of wall-clock changes.
    provider_failure_streak = 0  # Count adjacent provider failures, not all failures cumulatively.
    for number, item in enumerate(selected, start=1):  # Execute cases sequentially for understandable records.
        case = item["case"]  # Access the canonical question and expected answer.
        record = {  # Keep every attempted case traceable even when generation fails.
            **item,  # Copy dataset provenance and document reference into the result.
            "requested_document_id": mapping[case["tender_id"]],  # Choose the upload for this case's tender.
            "started_at": timestamp(),  # Record this attempt's start time.
            "status": "failed",  # Change to success only after output validation.
            "result": None,  # No answer/evidence exists until capture returns.
            "error": None,  # Retain the original compact error-name field.
            "error_details": None,  # Add safe diagnostic information for failures.
        }
        progress = {"stage": "capture_start"}  # Track how far this case progressed.
        case_started = time.perf_counter()  # Measure this case including failed execution.
        try:  # One failed case should not erase previous results or stop later cases.
            result = capture_case(case, record["requested_document_id"], progress=progress)  # Run against actual indexed data.
            progress["stage"] = "result_validation"  # Distinguish output issues from model/provider failures.
            if not isinstance(result.get("answer"), str) or not result["answer"].strip():  # Reject empty answers.
                raise ValueError("Empty answer.")
            evidence = result["evaluation_evidence"]  # Require the opt-in chain output.
            for field in ("retrieved_chunks", "structured_overview", "prompt_messages"):  # Check evaluation inputs exist.
                if field not in evidence:  # Missing evidence cannot support later metrics.
                    raise ValueError("Incomplete evaluation evidence.")
            json.dumps(result)  # Detect serialization failures before marking success.
            record["result"] = result  # Store the validated captured output.
            record["status"] = "success"  # Success means capture completed, not answer correctness.
        except Exception as exc:  # Preserve execution failures instead of grading them as factual errors.
            record["error"] = type(exc).__name__  # Retain compatibility with earlier reports.
            record["error_details"] = failure_details(exc, progress["stage"])  # Store safe diagnosis, not provider messages.
        record["elapsed_seconds"] = round(time.perf_counter() - case_started, 3)  # Include time spent on failures.
        record["finished_at"] = timestamp()  # Record when this attempt ended.
        report["results"].append(record)  # Account for this attempt in the denominator.
        details = record["error_details"] or {}  # Successful cases have no error details.
        code = details.get("http_status")  # Use safe provider status information where available.
        provider_failure = record["status"] == "failed" and (  # Separate service errors from local dataset/index failures.
            (type(code) is int and 400 <= code <= 599)  # Includes provider HTTP errors such as 429 and 503.
            or details.get("module", "").startswith("google.genai")  # Include provider failures without an HTTP code.
        )
        provider_failure_streak = provider_failure_streak + 1 if provider_failure else 0  # Reset on success or local failure.
        record["provider_failure_streak"] = provider_failure_streak  # Explain the counter at each attempted case.
        should_stop = provider_failure_streak >= max_consecutive_provider_failures and number < len(selected)  # Stop before another request.
        if should_stop:  # Preserve the reason and exact remaining selection in the checkpoint.
            report["status"] = "stopped_provider_failures"  # This is an incomplete run, not a completed baseline.
            report["stop_reason"] = f"{provider_failure_streak} consecutive provider failures; no automatic resume."
            report["not_attempted_ids"] = [remaining["case"]["id"] for remaining in selected[number:]]  # List work never executed.
        save_result(report, output)  # Preserve progress before starting another case.
        print(f"[{number}/{len(selected)}] {case['id']}: {record['status']}")  # Show concise progress.
        if record["error_details"]:  # Make diagnosis visible without opening the JSON file.
            print("Failure details:", record["error_details"])  # Contains no raw messages or credentials.
        if should_stop:  # Leave the loop immediately; do not sleep or submit another model request.
            print("Stopped:", report["stop_reason"])  # Make the early stop explicit to the user.
            print("Not attempted:", report["not_attempted_ids"])  # Show which cases may be selected in a later run.
            break  # A later retry is a separate explicitly launched run.
        if number < len(selected) and pause:  # Avoid sleeping after the final case.
            time.sleep(pause)  # Apply pacing without retrying failed requests.

    successful = sum(record["status"] == "success" for record in report["results"])  # Count completed captures.
    report["summary"] = {  # Keep failures visible alongside successful results.
        "planned": len(selected),  # Number of selected distinct questions.
        "recorded": len(report["results"]),  # Number of attempts actually recorded.
        "successful": successful,  # Captures available for later assessment.
        "failed": len(report["results"]) - successful,  # Count only actual failed attempts.
        "not_attempted": len(report["not_attempted_ids"]),  # Preserve the rest of the planned denominator.
    }
    if report["stop_reason"] is None:  # Preserve an early-stop status instead of calling it completed.
        report["status"] = "complete" if successful == len(selected) else "completed_with_failures"  # Describe run completion.
    report["elapsed_seconds"] = round(time.perf_counter() - started, 3)  # Includes pauses between cases.
    report["finished_at"] = timestamp()  # Record run completion time.
    save_result(report, output)  # Finalize the checkpoint with summary counts.
    print("Summary:", report["summary"])  # Show the denominators in the terminal.
    print("Saved:", output)  # Locate the artifact for inspection.
    return report  # Allow offline tests or main to inspect the final outcome.


def main():
    """Input: command-line arguments. Output: saved report; exits nonzero on failure.

    Validate paths, selections and mappings before calling the paid generation path.
    Default selection stays one question; --all explicitly expands to the full suite.
    """
    parser = argparse.ArgumentParser(description=__doc__)  # Use the module description for --help.
    parser.add_argument("--document-id", help="Upload ID for a selection containing only one tender.")  # Simple one-tender mapping.
    parser.add_argument("--document-map", action="append", default=[],  # Collect repeated tender/upload pairs.
                        help="TENDER_ID=UPLOAD_ID; repeat for each selected tender.")  # Explain required syntax.
    selection = parser.add_mutually_exclusive_group()  # Prevent mixing all cases with an explicit subset.
    selection.add_argument("--all", action="store_true", help="Capture all reviewed dataset cases.")  # Require explicit full-suite selection.
    selection.add_argument("--question-id", action="append", help="Question ID; repeat to select several.")  # Support small subsets.
    parser.add_argument("--dataset", type=Path, default=DATASET,
                        help="Versioned question JSON; default dataset_v1.json.")
    parser.add_argument("--pause", type=float, default=2.0, help="Seconds between cases; default 2.")  # Control pacing only.
    parser.add_argument("--max-consecutive-provider-failures", type=int, default=3,
                        help="Stop after this many adjacent provider failures; default 3.")  # Bound continued requests during provider trouble.
    args = parser.parse_args()  # Read and validate basic CLI syntax.
    if Path.cwd().resolve() != PROJECT_ROOT:  # SQLite and Chroma app paths depend on the working directory.
        parser.error(f"Run from {PROJECT_ROOT} to use the app's local storage.")  # Avoid opening unrelated local stores.
    if not (PROJECT_ROOT / "tenderiq_dev.db").is_file() or not (PROJECT_ROOT / "data/chroma").is_dir():  # Require existing ingestion.
        parser.error("Existing SQLite database and Chroma index are required. Upload PDFs first.")  # Do not ingest implicitly.
    if args.pause < 0 or not math.isfinite(args.pause):  # Reject negative, infinite and NaN delays.
        parser.error("--pause must be a finite nonnegative number.")  # Explain invalid pacing configuration.
    if args.max_consecutive_provider_failures < 1:  # Reject a threshold that cannot describe a real failure streak.
        parser.error("--max-consecutive-provider-failures must be at least 1.")
    question_ids = None if args.all else (args.question_id or ["T1-NEW-011"])  # Keep the default run inexpensive.
    if question_ids and len(question_ids) != len(set(question_ids)):  # Repeated IDs must not inflate counts.
        parser.error("Selected question IDs must be unique.")  # Require intentional distinct cases.
    try:  # Convert dataset/mapping problems into readable CLI errors.
        selected = load_cases(args.dataset, question_ids)  # Load canonical questions and references.
        mapping = document_mapping(selected, args.document_map, args.document_id)  # Resolve upload arguments.
    except (OSError, ValueError, KeyError, TypeError) as exc:  # Handle local input problems before generation.
        parser.error(str(exc))  # These are local validation messages, not provider response bodies.
    print("Selected cases:", len(selected))  # Make the planned scope visible.
    print("Generation model calls will be made. No judge calls or quality scores.")  # Explain execution and cost scope.
    report = capture_batch(selected, mapping, args.pause, args.max_consecutive_provider_failures)  # Apply the recorded stop policy.
    if report["summary"]["failed"] or report["summary"]["not_attempted"]:  # Scripts/CI should detect incomplete captures reliably.
        raise SystemExit(1)  # Return a failing exit code while keeping saved diagnostics.


if __name__ == "__main__":  # Importing this file must not start the experiment.
    main()  # Execute only when explicitly launched as a script.
