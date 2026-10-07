from types import SimpleNamespace

from tender_iq.api.schemas.chat import CitationSource
from tender_iq.services import chat


def test_is_basic_greeting_keeps_exact_and_short_greetings():
    assert chat._is_basic_greeting("  HELLO  ")
    assert chat._is_basic_greeting("hey there!")


def test_is_basic_greeting_does_not_intercept_compound_questions():
    assert not chat._is_basic_greeting("hey what is the emd?")
    assert not chat._is_basic_greeting("thanks what is the deadline?")
    assert not chat._is_basic_greeting("hello tell me the eligibility criteria")


def test_process_chat_query_cites_rag_sources(monkeypatch):
    stored_chunk = SimpleNamespace(
        metadata={"page_number": 1, "section": "Stored"},
        page_content="Stored chunk",
    )
    retrieved_chunk = SimpleNamespace(
        metadata={"page_number": 9, "subsection": "Retrieved"},
        page_content="Retrieved chunk",
    )

    monkeypatch.setattr(
        chat,
        "get_tender_by_id",
        lambda db, tender_id: SimpleNamespace(id=tender_id, bid_id=tender_id, specs={"bid_id": tender_id}),
    )
    monkeypatch.setattr(chat, "get_all_chunks_for_tender", lambda tender_id: [stored_chunk])
    monkeypatch.setattr(
        chat,
        "build_rag_chain",
        lambda **kwargs: SimpleNamespace(
            invoke=lambda query: {"answer": "Grounded answer", "sources": [retrieved_chunk]}
        ),
    )

    response = chat.process_chat_query(object(), "BID-1", "What is required?")

    assert response.answer == "Grounded answer"
    assert response.citations == [
        CitationSource(
            page_number=9,
            section="Retrieved",
            snippet="Retrieved chunk...",
        )
    ]
    assert set(response.latency_breakdown_ms) == {
        "chunk_loading_ms",
        "bm25_build_ms",
        "query_expansion_ms",
        "retrieval_ms",
        "answer_generation_ms",
    }
    assert response.latency_breakdown_ms["chunk_loading_ms"] >= 0

def test_job_id_chat_uses_bid_id_for_loading_and_retrieval(monkeypatch):
    requested_ids = []
    monkeypatch.setattr(chat, "get_tender_by_id", lambda db, tender_id: SimpleNamespace(
        id="JOB-1", bid_id="GEM/2022/B/2684984", specs={}
    ))
    def load_chunks(tender_id):
        requested_ids.append(tender_id)
        return [SimpleNamespace(page_content="EMD 25000", metadata={})]
    def build_chain(**kwargs):
        requested_ids.append(kwargs["tender_id"])
        return SimpleNamespace(invoke=lambda query: {"answer": "25000", "sources": []})
    monkeypatch.setattr(chat, "get_all_chunks_for_tender", load_chunks)
    monkeypatch.setattr(chat, "build_rag_chain", build_chain)
    response = chat.process_chat_query(object(), "JOB-1", "What is the EMD amount?")
    assert requested_ids == ["GEM/2022/B/2684984", "GEM/2022/B/2684984"]
    assert response.tender_id == "JOB-1"
    assert response.answer == "25000"
