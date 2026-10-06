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