"""
Chat service layer.
Coordinates SQLite, ChromaDB, and your existing LangChain RAG chain.
"""
import logging
from sqlalchemy.orm import Session
from langchain_core.documents import Document
import time

from tender_iq.crud.tenders import get_tender_by_id
from tender_iq.vector_store.chroma_store import get_vector_store
from tender_iq.rag.tender_rag import build_rag_chain
from tender_iq.api.schemas.chat import ChatResponse, CitationSource

logger = logging.getLogger(__name__)


class TenderNotFoundError(Exception):
    pass


class TenderDocumentsNotFoundError(Exception):
    pass


def _is_basic_greeting(query: str) -> bool:
    """Return True for simple conversational greetings and polite chitchat."""
    if not query:
        return False

    normalized = " ".join(query.strip().lower().split())
    greeting_set = {
        "hi",
        "hello",
        "hey",
        "greetings",
        "thanks",
        "thank you",
        "thankyou",
        "good morning",
        "good afternoon",
        "good evening",
    }

    greeting_set.add("hey there")
    return normalized.rstrip("!.?") in greeting_set


def get_all_chunks_for_tender(tender_id: str) -> list[Document]:
    """
    Reconstructs the chunks list from ChromaDB for BM25/Ensemble retrieval,
    matching how Streamlit used to pass them in memory.
    """
    vector_store = get_vector_store()
    # Query ChromaDB's underlying collection using the metadata filter
    results = vector_store._collection.get(
        where={"tender_id": tender_id},
        include=["documents", "metadatas"]
    )
    
    docs = []
    contents = results.get("documents", [])
    metadatas = results.get("metadatas", [])
    
    for content, meta in zip(contents, metadatas):
        docs.append(Document(page_content=content, metadata=meta))
        
    return docs

def process_chat_query(db: Session, tender_id: str, query: str) -> ChatResponse:
    normalized_query = " ".join(query.strip().lower().split())

    if _is_basic_greeting(normalized_query):
        return ChatResponse(
            tender_id=tender_id,
            answer="Hello! I am your TenderIQ assistant. How can I help you analyze this tender document today?",
            citations=[],
            latency_ms=0.0,
            latency_breakdown_ms={
                "chunk_loading_ms": 0.0,
                "bm25_build_ms": 0.0,
                "query_expansion_ms": 0.0,
                "retrieval_ms": 0.0,
                "answer_generation_ms": 0.0,
            },
            tokens_used=0
        )

    # 1. Fetch structured regex specs from SQLite
    db_tender = get_tender_by_id(db, tender_id)
    if not db_tender:
        raise TenderNotFoundError
    
    tender_specs = db_tender.specs
    vector_tender_id = db_tender.bid_id or db_tender.id

    # 2. Fetch all chunks from ChromaDB
    stage_latencies_ms = {
        "chunk_loading_ms": 0.0,
        "bm25_build_ms": 0.0,
        "query_expansion_ms": 0.0,
        "retrieval_ms": 0.0,
        "answer_generation_ms": 0.0,
    }
    chunk_load_start = time.perf_counter()
    try:
        chunks = get_all_chunks_for_tender(vector_tender_id)
    finally:
        stage_latencies_ms["chunk_loading_ms"] = round(
            (time.perf_counter() - chunk_load_start) * 1000, 2
        )
        logger.info(
            "Stage [Chunk Loading] completed in %.2f ms",
            stage_latencies_ms["chunk_loading_ms"],
        )
    if not chunks:
        raise TenderDocumentsNotFoundError

    # 3. Build the RAG chain
    rag_chain = build_rag_chain(
        tender_id=vector_tender_id,
        chunk=chunks,
        tender_obj=tender_specs,
        stage_latencies_ms=stage_latencies_ms,
    )

    rag_started_at = time.perf_counter()
    rag_result = rag_chain.invoke(query)
    latency_ms = round((time.perf_counter() - rag_started_at) * 1000, 2)
    stage_latencies_ms.update(rag_result.get("latency_breakdown_ms", {}))

    answer = rag_result["answer"]
    tokens_used = rag_result.get("tokens_used")  # Safely read from chain output

    # 5. Build citations
    citations = []
    for chunk in rag_result["sources"][:3]:
        meta = chunk.metadata
        citations.append(
            CitationSource(
                page_number=meta.get("page_number"),
                section=meta.get("subsection") or meta.get("section"),
                snippet=chunk.page_content[:250] + "..."
            )
        )

    return ChatResponse(
        tender_id=tender_id,
        answer=answer,
        citations=citations,
        latency_ms=latency_ms,
        latency_breakdown_ms=stage_latencies_ms,
        tokens_used=tokens_used
    )