from types import SimpleNamespace

from tender_iq.api.v1.endpoints import tenders as tenders_endpoint


def test_specification_endpoint_sanitizes_legacy_failure_status(monkeypatch):
    monkeypatch.setattr(
        tenders_endpoint.crud_tender,
        "get_tender_by_id",
        lambda db, tender_id: SimpleNamespace(
            id=tender_id,
            status="failed: sensitive database details",
            specs={},
        ),
    )

    response = tenders_endpoint.specification_tender("JOB-123", object())

    assert response.status == "failed"