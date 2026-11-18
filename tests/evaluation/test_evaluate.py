"""Offline contract tests: synthetic captures and real RAGAS with a scripted LLM."""

import asyncio
import copy
import hashlib
import json
from types import SimpleNamespace

import pytest

from tender_iq.evaluation import evaluate as ev


def write_json(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def collection(tmp_path):
    """A self-contained dataset and capture; no archived files or model calls."""
    case = {
        "id": "CASE-1", "question": "Is startup relaxation granted?",
        "expected_answer": "No", "answerable": True, "tender_id": "BID-1",
        "evidence": [{"page": 1, "section": "Startup relaxation"}],
    }
    document = {"pdf_path": "docs/source.pdf", "sha256": "0" * 64}
    dataset = {"schema_version": 1, "dataset_version": "v1",
               "documents": {"BID-1": document}, "cases": [case]}
    dataset_hash = write_json(tmp_path / "dataset.json", dataset)
    overview = "Bid ID: BID-1"
    chunk = {"chunk_id": "chunk-1", "position": 1,
             "text": "Startup Relaxation: No", "metadata": {"page_number": 1}}
    record = {
        "case": case, "status": "success", "dataset_sha256": dataset_hash,
        "dataset_version": "v1", "error": None,
        "document_reference": {"tender": "BID-1", **document},
        "result": {
            "answer": "Startup relaxation is provided.", "resolved_job_id": "JOB-1",
            "vector_tender_id": "BID-1",
            "evaluation_evidence": {
                "retrieved_chunks": [chunk], "structured_overview": overview,
                "prompt_messages": [{"content": case["question"] + overview + chunk["text"]}],
            },
        },
    }
    entry = {"capture_run_id": "RUN-1", "json_pointer": "/results/0",
             "question_id": case["id"], "answerable": True}
    capture = {"schema_version": 1, "run_id": "RUN-1", "status": "complete",
               "dataset_version": "v1", "dataset_sha256": dataset_hash,
               "planned_cases": 1, "not_attempted_ids": [], "results": [record]}
    path = tmp_path / "capture.json"
    write_json(path, capture)
    return tmp_path, path, capture, {"locator": entry, "record": record}


def test_valid_fixed_collection(collection):
    root, path, _, _ = collection
    capture, provenance, cases = ev.load_inputs(path, root / "dataset.json")
    assert len(cases) == 1 and capture["run_id"] == "RUN-1"
    assert provenance["capture_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize("mutation", ["hash", "case", "duplicate", "lost_attempt", "missing_prompt", "unfinished"])
def test_invalid_provenance_stops_before_scoring(collection, mutation):
    root, path, capture, _ = collection
    if mutation == "hash":
        capture["dataset_sha256"] = "0" * 64
    elif mutation == "case":
        capture["results"][0]["case"]["expected_answer"] = "Different reference"
    elif mutation == "duplicate":
        capture["results"] *= 2
    elif mutation == "lost_attempt":
        capture["planned_cases"] = 2
    elif mutation == "unfinished":
        capture["status"] = "running"
    else:
        capture["results"][0]["result"]["evaluation_evidence"]["prompt_messages"] = []
    write_json(path, capture)
    with pytest.raises(ValueError):
        ev.load_inputs(path, root / "dataset.json")


def test_dataset_rejects_duplicate_questions(collection):
    root = collection[0]
    path = root / "dataset.json"
    dataset = json.loads(path.read_text())
    dataset["cases"] *= 2
    write_json(path, dataset)
    with pytest.raises(ValueError, match="unique"):
        ev.load_dataset(path)


def test_dataset_rejects_old_alias_columns(collection):
    path = collection[0] / "dataset.json"
    dataset = json.loads(path.read_text())
    dataset["cases"][0]["response"] = "Old duplicate reference"
    write_json(path, dataset)
    with pytest.raises(ValueError, match="minimal dataset schema"):
        ev.load_dataset(path)


def test_mapping_uses_actual_evidence_and_hides_human_feedback(collection):
    item = collection[3]
    item["record"]["case"].update(human_label="SECRET", retrieved_contexts=["NOT REAL RETRIEVAL"])
    sample = ev.to_ragas_sample(item)
    assert sample["retrieved_contexts"] == ["Startup Relaxation: No", "Bid ID: BID-1"]
    assert "SECRET" not in json.dumps(sample)
    assert "NOT REAL RETRIEVAL" not in json.dumps(sample)


class FixedMetric:
    def __init__(self, value=None, reason=None, error=None):
        self.result = SimpleNamespace(value=value, reason=reason)
        self.error = error

    async def ascore(self, **kwargs):
        if self.error:
            raise self.error
        return self.result


def test_metric_failure_does_not_discard_other_score(collection):
    metrics = {"correctness": FixedMetric("wrong", "Contradicts No."),
               "faithfulness": FixedMetric(error=RuntimeError("PRIVATE provider error"))}
    row = asyncio.run(ev.score_case(collection[3], metrics, None))
    summary = ev.summarize([row], 2)
    assert summary["correctness"]["label_counts"] == {"wrong": 1}
    assert summary["faithfulness"]["completed"] == 0
    assert summary["faithfulness"]["mean"] is None
    assert summary["not_attempted"] == 1
    assert "PRIVATE" not in json.dumps(row)


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), -1, 2])
def test_undefined_or_invalid_faithfulness_never_enters_average(collection, invalid):
    metrics = {"correctness": FixedMetric("wrong", "Contradiction."), "faithfulness": FixedMetric(invalid)}
    row = asyncio.run(ev.score_case(collection[3], metrics, None))
    assert row["metrics"]["faithfulness"]["value"] is None
    assert ev.summarize([row], 1)["faithfulness"]["failed"] == 1


def test_clean_negative_cannot_be_labeled_correct(collection):
    item = copy.deepcopy(collection[3])
    item["record"]["case"]["answerable"] = False
    metrics = {"correctness": FixedMetric("correct", "An absence answer."), "faithfulness": FixedMetric(1)}
    result = asyncio.run(ev.score_case(item, metrics, None))["metrics"]["correctness"]
    assert result["error"] == "InconsistentAbstentionLabel"
    assert result["rejected_value"] == "correct"


def test_actual_ragas_claim_pipeline_without_network(collection, monkeypatch):
    """Exercise installed RAGAS schemas/algorithms with deterministic LLM responses."""
    monkeypatch.setenv("RAGAS_DO_NOT_TRACK", "true")
    from ragas.llms.base import InstructorBaseRagasLLM

    class ScriptedLLM(InstructorBaseRagasLLM):
        def __init__(self):
            self.calls = []

        def generate(self, prompt, response_model):
            raise AssertionError("Only async calls expected.")

        async def agenerate(self, prompt, response_model):
            self.calls.append((prompt, response_model.__name__))
            responses = {
                "DiscreteResponseModel": {"value": "wrong", "reason": "Relaxation contradicts No."},
                "StatementGeneratorOutput": {"statements": ["Startup relaxation is provided."]},
                "NLIStatementOutput": {"statements": [{"statement": "Startup relaxation is provided.", "verdict": 0, "reason": "The field says No."}]},
            }
            return response_model.model_validate(responses[response_model.__name__])

    llm = ScriptedLLM()
    row = asyncio.run(ev.score_case(collection[3], ev.build_metrics(llm), llm))
    assert row["metrics"]["correctness"]["value"] == "wrong"
    assert row["metrics"]["faithfulness"]["value"] == 0
    assert len(llm.calls) == 3  # One rubric call; statement generation and support check.
    assert "Bid ID: BID-1" in llm.calls[-1][0]  # Overview participates in support checking.


def test_real_sdk_and_instructor_protocol_without_network(collection, monkeypatch):
    """Catch adapter/API mismatches using a local HTTP transport, never a provider."""
    monkeypatch.setenv("RAGAS_DO_NOT_TRACK", "true")
    import httpx
    from openai import AsyncOpenAI
    from ragas.llms import llm_factory

    requests = []
    def respond(request):
        body = json.loads(request.content)
        requests.append(body)
        assert body["response_format"] == {"type": "json_object"}
        payloads = [
            {"value": "wrong", "reason": "Contradicts the No field."},
            {"statements": ["Startup relaxation is provided."]},
            {"statements": [{"statement": "Startup relaxation is provided.", "reason": "The field says No.", "verdict": 0}]},
        ]
        return httpx.Response(200, json={
            "id": "local-test", "object": "chat.completion", "created": 0,
            "model": body["model"],
            "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant", "content": json.dumps(payloads[len(requests) - 1]),
            }}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        })

    async def run():
        client = AsyncOpenAI(
            api_key="dummy-offline-key", base_url="https://offline.invalid/v1",
            max_retries=0, http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond)),
        )
        try:
            llm = llm_factory(
                "openai/gpt-4o-mini", client=client, adapter="instructor",
                temperature=0, top_p=1, max_tokens=4096, max_retries=1,
            )
            return await asyncio.wait_for(ev.score_case(collection[3], ev.build_metrics(llm), llm, timeout=2), timeout=6)
        finally:
            await client.close()

    row = asyncio.run(run())
    assert row["metrics"]["faithfulness"]["value"] == 0
    assert row["metrics"]["correctness"]["value"] == "wrong"
    assert len(requests) == 3
    assert all(body["temperature"] == 0 and body["max_tokens"] == 4096 for body in requests)


def test_run_checkpoints_partial_results_and_closes_client(collection, monkeypatch, tmp_path):
    root, path, capture, item = collection
    class Client:
        closed = False
        async def close(self):
            self.closed = True
    client = Client()
    metrics = {"correctness": FixedMetric("wrong", "Contradiction."), "faithfulness": FixedMetric(float("nan"))}
    monkeypatch.setattr(ev, "create_runtime", lambda: (client, None, metrics, {"metric_timeout_seconds": 2}))
    report = asyncio.run(ev.run_scores([item], capture, {"capture_path": str(path)}, root / "scores"))
    saved = json.loads(next((root / "scores").glob("*.json")).read_text())
    assert client.closed and report["status"] == "incomplete"
    assert saved["results"][0]["metrics"]["correctness"]["value"] == "wrong"
    assert not list((root / "scores").glob("*.tmp"))


def test_cli_offline_does_not_configure_judge(collection, monkeypatch):
    root, path, _, item = collection
    monkeypatch.setattr(ev, "load_inputs", lambda *_: ({"results": []}, {}, [item]))
    monkeypatch.setattr(ev, "create_runtime", lambda: pytest.fail("Offline mode must not configure a judge."))
    monkeypatch.setattr("sys.argv", ["evaluate", "--capture", str(path), "--all"])
    ev.main()


def test_capture_and_score_use_the_same_dataset_format(collection, monkeypatch):
    from tender_iq.evaluation import capture_evidence as cap

    root, _, _, item = collection
    monkeypatch.setattr(cap, "RESULTS_DIR", root / "captures")
    monkeypatch.setattr(cap, "capture_case", lambda *args, **kwargs: copy.deepcopy(item["record"]["result"]))
    selected = cap.load_cases(root / "dataset.json")
    report = cap.capture_batch(selected, {"BID-1": "JOB-1"}, pause=0)
    path = next((root / "captures").glob("*.json"))
    loaded, _, cases = ev.load_inputs(path, root / "dataset.json")
    assert report["summary"]["successful"] == 1
    assert loaded["dataset_version"] == "v1" and len(cases) == 1


def test_capture_provider_stop_preserves_unattempted_ids(collection, monkeypatch):
    from tender_iq.evaluation import capture_evidence as cap

    root, _, _, item = collection
    dataset_path = root / "dataset.json"
    dataset = json.loads(dataset_path.read_text())
    dataset["cases"].append({**dataset["cases"][0], "id": "CASE-2"})
    write_json(dataset_path, dataset)
    monkeypatch.setattr(cap, "RESULTS_DIR", root / "captures")
    class ProviderError(Exception):
        code = 503
    def fail(*args, **kwargs):
        raise ProviderError("PRIVATE provider details")
    monkeypatch.setattr(cap, "capture_case", fail)
    report = cap.capture_batch(cap.load_cases(dataset_path), {"BID-1": "JOB-1"}, pause=0, max_consecutive_provider_failures=1)
    assert report["summary"] == {"planned": 2, "recorded": 1, "successful": 0, "failed": 1, "not_attempted": 1}
    assert report["not_attempted_ids"] == ["CASE-2"]
    assert "PRIVATE" not in json.dumps(report)


def test_score_retrieval_offline(collection, tmp_path):
    root, capture_path, _, item = collection
    dataset_path = root / "dataset.json"

    # Prepare capture with 5 chunks
    capture = json.loads(capture_path.read_text())
    chunks = [
        {"chunk_id": f"chunk-{i}", "position": i, "text": f"Evidence text {i}", "metadata": {}}
        for i in range(1, 6)
    ]
    capture["results"][0]["result"]["evaluation_evidence"]["retrieved_chunks"] = chunks
    capture_hash = write_json(capture_path, capture)

    dataset = json.loads(dataset_path.read_text())
    dataset_hash = hashlib.sha256(dataset_path.read_bytes()).hexdigest()

    labels_data = {
        "schema_version": 1,
        "dataset_sha256": dataset_hash,
        "capture_sha256": capture_hash,
        "metric": "precision_at_5_saved_union_order",
        "k": 5,
        "included_cases": ["CASE-1"],
        "excluded_cases": {},
        "labels": {
            "CASE-1": [
                {"position": 1, "chunk_id": "chunk-1", "relevant": True, "reason": "Supports answer."},
                {"position": 2, "chunk_id": "chunk-2", "relevant": False, "reason": "Irrelevant."},
                {"position": 3, "chunk_id": "chunk-3", "relevant": True, "reason": "Supports answer."},
                {"position": 4, "chunk_id": "chunk-4", "relevant": False, "reason": "Irrelevant."},
                {"position": 5, "chunk_id": "chunk-5", "relevant": False, "reason": "Irrelevant."},
            ]
        }
    }
    labels_path = tmp_path / "retrieval_labels.json"
    write_json(labels_path, labels_data)

    out_dir = tmp_path / "scores"
    report = ev.score_retrieval(capture_path, dataset_path, labels_path, output_dir=out_dir)

    assert report["status"] == "complete"
    assert report["summary"]["included_cases"] == 1
    assert report["summary"]["mean_precision_at_5"] == 0.4
    assert report["results"][0]["precision_at_5"] == 0.4
    assert report["results"][0]["relevant_count"] == 2
    assert list(out_dir.glob("retrieval_scores_*.json"))


def test_score_retrieval_hash_mismatch(collection, tmp_path):
    root, capture_path, _, _ = collection
    dataset_path = root / "dataset.json"

    labels_data = {
        "schema_version": 1,
        "dataset_sha256": "wrong_hash",
        "capture_sha256": "wrong_hash",
        "metric": "precision_at_5_saved_union_order",
        "k": 5,
        "included_cases": ["CASE-1"],
        "excluded_cases": {},
        "labels": {}
    }
    labels_path = tmp_path / "bad_labels.json"
    write_json(labels_path, labels_data)

    with pytest.raises(ValueError, match="dataset hash mismatch"):
        ev.score_retrieval(capture_path, dataset_path, labels_path)


def test_capture_records_traceable_provenance_and_no_secrets(collection, monkeypatch):
    from tender_iq.evaluation import capture_evidence as cap

    root, _, _, item = collection
    dataset_path = root / "dataset.json"
    monkeypatch.setattr(cap, "RESULTS_DIR", root / "captures")
    monkeypatch.setattr(cap, "capture_case", lambda *args, **kwargs: copy.deepcopy(item["record"]["result"]))

    mapping = {"BID-1": "JOB-1"}
    report = cap.capture_batch(cap.load_cases(dataset_path), mapping, pause=0)

    # 1. Capture includes git revision and configuration fields
    assert "provenance" in report
    prov = report["provenance"]
    assert "git" in prov and "commit_sha" in prov["git"] and "branch" in prov["git"]
    assert prov["models"]["generation"]["model"] == "gemini-3.1-flash-lite"
    assert prov["models"]["embeddings"]["model"] == "all-MiniLM-L6-v2"
    assert prov["retrieval_settings"]["search_type"] == "mmr"
    assert prov["retrieval_settings"]["ensemble_weights"] == [0.4, 0.6]
    assert prov["upload_mappings"] == mapping
    assert "BID-1" in prov["documents"]

    # 2. Sensitive environment values / API keys are not written into report
    serialized = json.dumps(report)
    for forbidden in ["API_KEY", "SECRET", "PASSWORD", "TOKEN", "Bearer", "AIzaSy"]:
        assert forbidden not in serialized


def test_score_report_records_exact_capture(collection, tmp_path):
    root, capture_path, _, _ = collection
    dataset_path = root / "dataset.json"

    capture = json.loads(capture_path.read_text())
    chunks = [
        {"chunk_id": f"chunk-{i}", "position": i, "text": f"Text {i}", "metadata": {}}
        for i in range(1, 6)
    ]
    capture["results"][0]["result"]["evaluation_evidence"]["retrieved_chunks"] = chunks
    capture_hash = write_json(capture_path, capture)

    dataset = json.loads(dataset_path.read_text())
    dataset_hash = hashlib.sha256(dataset_path.read_bytes()).hexdigest()

    labels_data = {
        "schema_version": 1,
        "dataset_sha256": dataset_hash,
        "capture_sha256": capture_hash,
        "metric": "precision_at_5_saved_union_order",
        "k": 5,
        "included_cases": ["CASE-1"],
        "excluded_cases": {},
        "labels": {
            "CASE-1": [{"position": i, "chunk_id": f"chunk-{i}", "relevant": True, "reason": "ok"} for i in range(1, 6)]
        }
    }
    labels_path = tmp_path / "labels.json"
    write_json(labels_path, labels_data)

    out_dir = tmp_path / "scores"
    report = ev.score_retrieval(capture_path, dataset_path, labels_path, output_dir=out_dir)

    assert report["inputs"]["capture_sha256"] == capture_hash
    assert report["inputs"]["capture_path"] == str(capture_path.resolve())
    assert report["inputs"]["dataset_sha256"] == dataset_hash


