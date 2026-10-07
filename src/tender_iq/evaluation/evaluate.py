"""Evaluate TenderIQ's RAG pipeline with RAGAS."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import types
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from datasets import Dataset
from dotenv import load_dotenv
from langchain_core.documents import Document

load_dotenv()


@dataclass(frozen=True)
class EvaluationCase:
    question: str
    ground_truth: str
    retrieved_contexts: list[str]
    tender_id: str | None
    source: Path
    index: int


def _case_text(
    item: dict[str, Any],
    keys: tuple[str, ...],
    field: str,
    source: Path,
    index: int,
) -> str:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    raise ValueError(f"{source}: item {index} must contain a non-empty {field} field.")


def _read_items(path: Path) -> list[dict[str, Any]]:
    try:
        content = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unable to read evaluation dataset {path}: {exc}") from exc

    if isinstance(content, list):
        items = content
    elif isinstance(content, dict):
        items = content.get("eval_dataset", content.get("data"))
    else:
        items = None

    if not isinstance(items, list):
        raise ValueError(
            f"{path}: expected a list or an object with an 'eval_dataset' or 'data' list."
        )
    if any(not isinstance(item, dict) for item in items):
        raise ValueError(f"{path}: every evaluation item must be a JSON object.")
    return items


def load_test_cases(dataset_dir: Path) -> list[EvaluationCase]:
    """Load and validate supported benchmark JSON files from a directory tree."""
    if not dataset_dir.is_dir():
        raise ValueError(f"Evaluation dataset directory does not exist: {dataset_dir}")

    reports_dir = dataset_dir / "reports"
    dataset_paths = sorted(
        path
        for path in dataset_dir.rglob("*.json")
        if reports_dir not in path.parents
    )
    if not dataset_paths:
        raise ValueError(f"No JSON evaluation datasets found under {dataset_dir}")

    cases: list[EvaluationCase] = []
    for path in dataset_paths:
        for index, item in enumerate(_read_items(path), start=1):
            contexts = item.get("retrieved_contexts", [])
            if isinstance(contexts, str):
                contexts = [contexts]
            if not isinstance(contexts, list) or any(
                not isinstance(context, str) for context in contexts
            ):
                raise ValueError(
                    f"{path}: item {index} field 'retrieved_contexts' must be a string or list of strings."
                )
            tender_id = item.get("tender_id")
            if tender_id is not None and (
                not isinstance(tender_id, str) or not tender_id.strip()
            ):
                raise ValueError(
                    f"{path}: item {index} field 'tender_id' must be a non-empty string."
                )
            cases.append(
                EvaluationCase(
                    question=_case_text(
                        item, ("user_input", "question"), "question", path, index
                    ),
                    ground_truth=_case_text(
                        item, ("response", "ground_truth"), "ground truth", path, index
                    ),
                    retrieved_contexts=[context for context in contexts if context.strip()],
                    tender_id=tender_id.strip() if tender_id else None,
                    source=path,
                    index=index,
                )
            )

    if not cases:
        raise ValueError(f"No evaluation cases found under {dataset_dir}")
    return cases


def _run_rag(case: EvaluationCase, tender_id_override: str | None) -> tuple[str, list[str]]:
    """Generate a live answer and return the contexts actually retrieved by the chain."""
    from tender_iq.rag.tender_rag import build_rag_chain

    tender_id = case.tender_id or tender_id_override
    if tender_id:
        from tender_iq.crud.tenders import get_tender_by_id
        from tender_iq.db.session import SessionLocal
        from tender_iq.services.chat import get_all_chunks_for_tender

        db = SessionLocal()
        try:
            tender = get_tender_by_id(db, tender_id)
            if tender is None:
                raise ValueError(f"Tender '{tender_id}' was not found in the database.")
            vector_tender_id = tender.bid_id or tender.id
            chunks = get_all_chunks_for_tender(vector_tender_id)
            if not chunks and vector_tender_id != tender.id:
                vector_tender_id = tender.id
                chunks = get_all_chunks_for_tender(vector_tender_id)
            if not chunks:
                raise ValueError(
                    f"No ChromaDB documents were found for tender '{tender_id}'."
                )
            chain = build_rag_chain(
                tender_id=vector_tender_id,
                chunk=chunks,
                tender_obj=tender.specs,
            )
        finally:
            db.close()
    elif case.retrieved_contexts:
        # Existing benchmark files carry their own contexts but no tender IDs.
        vector_tender_id = f"evaluation-{case.source.stem}-{case.index}"
        chunks = [
            Document(
                page_content=context,
                metadata={"tender_id": vector_tender_id},
            )
            for context in case.retrieved_contexts
        ]
        chain = build_rag_chain(
            tender_id=vector_tender_id,
            chunk=chunks,
        )
    else:
        raise ValueError(
            f"{case.source}: item {case.index} needs a tender_id or retrieved_contexts."
        )

    try:
        result = chain.invoke(case.question)
    except Exception as exc:
        raise RuntimeError(
            f"RAG chain failed for {case.source}, item {case.index}: {exc}"
        ) from exc

    answer = result.get("answer")
    sources = result.get("sources")
    if not isinstance(answer, str) or not answer.strip():
        raise RuntimeError(
            f"RAG chain returned no answer for {case.source}, item {case.index}."
        )
    if not isinstance(sources, list):
        raise RuntimeError(
            f"RAG chain returned invalid sources for {case.source}, item {case.index}."
        )
    return answer.strip(), [
        source.page_content
        for source in sources
        if isinstance(source, Document) and source.page_content.strip()
    ]


def _load_ragas_components() -> tuple[Any, list[Any], Any, Any]:
    """Load RAGAS configured for OpenRouter LLM and HuggingFace embeddings."""
    legacy_vertex_module = "langchain_community.chat_models.vertexai"
    if importlib.util.find_spec(legacy_vertex_module) is None:
        shim = types.ModuleType(legacy_vertex_module)
        shim.ChatVertexAI = type("ChatVertexAI", (), {})
        sys.modules[legacy_vertex_module] = shim

    try:
        from langchain_openai import ChatOpenAI
        from langchain_huggingface import HuggingFaceEmbeddings
        from ragas import evaluate
        from ragas.embeddings import LangchainEmbeddingsWrapper
        from ragas.llms import LangchainLLMWrapper
        from ragas.metrics import (
            AnswerRelevancy,
            ContextPrecision,
            Faithfulness,
            LLMContextRecall,
        )
    except (ImportError, ModuleNotFoundError) as exc:
        raise RuntimeError(
            "RAGAS evaluation dependencies could not be imported. "
            "Run `uv sync` and verify the RAGAS/LangChain dependency versions."
        ) from exc

    # Retrieve OpenRouter key from environment
    openrouter_api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not openrouter_api_key:
        raise RuntimeError("OPENROUTER_API_KEY is required to evaluate via OpenRouter.")

    llm = LangchainLLMWrapper(
        ChatOpenAI(
            model=os.getenv("TENDERIQ_EVAL_LLM", "openai/gpt-4o-mini"),
            temperature=0,
            base_url="https://openrouter.ai/api/v1",
            api_key=openrouter_api_key,
        )
    )
    
    # Use local HuggingFace embeddings since OpenRouter doesn't provide embeddings
    embeddings = LangchainEmbeddingsWrapper(
        HuggingFaceEmbeddings(
            model_name=os.getenv("TENDERIQ_EVAL_EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        )
    )
    
    return (
        evaluate,
        [
            Faithfulness(),
            AnswerRelevancy(),
            ContextPrecision(),
            LLMContextRecall(),
        ],
        llm,
        embeddings,
    )


def run_evaluation(
    dataset_dir: Path,
    tender_id: str | None = None,
    report_dir: Path | None = None,
) -> pd.DataFrame:
    """Run TenderIQ over all JSON cases, score them, and save a timestamped CSV."""
    if not os.getenv("OPENAI_API_KEY") and not os.getenv("OPENROUTER_API_KEY"):
        raise RuntimeError(
            "OPENAI_API_KEY or OPENROUTER_API_KEY is required for RAGAS scoring."
        )
    cases = load_test_cases(dataset_dir)
    rows: list[dict[str, Any]] = []
    for case in cases:
        try:
            answer, contexts = _run_rag(case, tender_id)
        except Exception as exc:
            raise RuntimeError(
                f"Evaluation stopped at {case.source}, item {case.index}: {exc}"
            ) from exc
        rows.append(
            {
                "question": case.question,
                "answer": answer,
                "retrieved_contexts": contexts,
                "ground_truth": case.ground_truth,
            }
        )

    dataset = Dataset.from_list(rows)
    evaluate, metrics, llm, embeddings = _load_ragas_components()
    result = evaluate(
        dataset,
        metrics=metrics,
        llm=llm,
        embeddings=embeddings,
        column_map={
            "user_input": "question",
            "response": "answer",
            "reference": "ground_truth",
        },
        raise_exceptions=True,
    )

    scores = result.to_pandas()
    if "answer_relevancy" in scores.columns:
        scores = scores.rename(columns={"answer_relevancy": "answer_relevance"})

    output_dir = report_dir or Path(__file__).parent / "reports"
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    report_path = output_dir / f"ragas_scores_{timestamp}.csv"
    scores.to_csv(report_path, index=False)

    metric_names = [
        "faithfulness",
        "answer_relevance",
        "context_precision",
        "context_recall",
    ]
    available_metrics = [name for name in metric_names if name in scores.columns]
    summary = scores[available_metrics].mean(numeric_only=True).to_frame("mean").T
    print(f"Evaluated {len(rows)} cases. Report: {report_path}")
    print(summary.to_string(index=False, float_format=lambda score: f"{score:.4f}"))
    return scores


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=Path(__file__).parent,
        help="Directory to recursively scan for benchmark JSON files.",
    )
    parser.add_argument(
        "--tender-id",
        help="Optional default tender ID for cases without a per-item tender_id.",
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        help="CSV report directory (defaults to evaluation/reports).",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    try:
        run_evaluation(args.dataset_dir, args.tender_id, args.report_dir)
    except (RuntimeError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc

if __name__ == "__main__":
    main()
