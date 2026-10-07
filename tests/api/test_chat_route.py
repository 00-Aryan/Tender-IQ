# tests/api/test_chat_route.py
from fastapi.testclient import TestClient
from tender_iq.api.v1.endpoints import chat as chat_endpoint
from tender_iq.main import app
from tender_iq.api.schemas.chat import ChatResponse

client = TestClient(app)

def test_chat_endpoint_short_query_fails():
    payload = {"tender_id": "GEM-2026-101", "query": "?"}
    response = client.post("/api/v1/chat/", json=payload)
    assert response.status_code == 422

def test_chat_endpoint_valid_payload(monkeypatch):
    payload = {
        "tender_id": "GEM-2026-101",
        "query": "What is the contract duration?",
    }
    monkeypatch.setattr(
        chat_endpoint,
        "process_chat_query",
        lambda db, tender_id, query: ChatResponse(
            tender_id=tender_id,
            answer="The contract duration is 24 months.",
        ),
    )

    response = client.post("/api/v1/chat/", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["tender_id"] == "GEM-2026-101"
    assert "citations" in data


def test_chat_endpoint_returns_safe_not_found_detail(monkeypatch):
    def raise_tender_not_found(**kwargs):
        raise chat_endpoint.TenderNotFoundError("internal tender lookup detail")

    monkeypatch.setattr(chat_endpoint, "process_chat_query", raise_tender_not_found)

    response = client.post(
        "/api/v1/chat/",
        json={"tender_id": "GEM-2026-101", "query": "What is the deadline?"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Requested tender not found."}


def test_chat_endpoint_returns_generic_detail_for_unexpected_error(monkeypatch):
    def raise_internal_error(**kwargs):
        raise RuntimeError("database connection string")

    monkeypatch.setattr(chat_endpoint, "process_chat_query", raise_internal_error)

    response = client.post(
        "/api/v1/chat/",
        json={"tender_id": "GEM-2026-101", "query": "What is the deadline?"},
    )

    assert response.status_code == 500
    assert response.json() == {
        "detail": "An internal error occurred while processing your request. Please try again."
    }

def test_chat_endpoint_rejects_whitespace_only_fields(monkeypatch):
    def should_not_run(**kwargs):
        raise AssertionError("Blank inputs reached the service")
    monkeypatch.setattr(chat_endpoint, "process_chat_query", should_not_run)
    for payload in (
        {"tender_id": "BID-1", "query": "   "},
        {"tender_id": "   ", "query": "What is the EMD?"},
        {"tender_id": "BID-1", "query": " ? "},
    ):
        assert client.post("/api/v1/chat/", json=payload).status_code == 422


def test_chat_endpoint_trims_valid_fields_before_service(monkeypatch):
    received = []
    def respond(db, tender_id, query):
        received.append((tender_id, query))
        return ChatResponse(tender_id=tender_id, answer="25000")
    monkeypatch.setattr(chat_endpoint, "process_chat_query", respond)
    response = client.post("/api/v1/chat/", json={"tender_id": " BID-1 ", "query": " What is the EMD? "})
    assert response.status_code == 200
    assert received == [("BID-1", "What is the EMD?")]
