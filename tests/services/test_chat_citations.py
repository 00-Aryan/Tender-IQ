from types import SimpleNamespace

from tender_iq.api.schemas.chat import CitationSource
from tender_iq.services import chat


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
        lambda db, tender_id: SimpleNamespace(specs={"bid_id": tender_id}),
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