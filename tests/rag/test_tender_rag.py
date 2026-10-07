from tender_iq.rag.tender_rag import format_tender_metadata
from langchain_core.runnables import Runnable
from tender_iq.rag import tender_rag
from langchain_core.documents import Document
from langchain_core.runnables import RunnableLambda
from tender_iq.rag.query_transformers import build_multi_query_retrieval_chain


class DummyDates:
    def __init__(self, contract_period, duration_months, submission_deadline, opening_date):
        self.contract_period = contract_period
        self.duration_months = duration_months
        self.submission_deadline = submission_deadline
        self.opening_date = opening_date


class DummyFinancials:
    def __init__(self, estimated_bid_value, emd_amount):
        self.estimated_bid_value = estimated_bid_value
        self.emd_amount = emd_amount


class DummyFleet:
    def __init__(self, vehicle_type, minimum_quantity, estimated_km_per_month):
        self.vehicle_type = vehicle_type
        self.minimum_quantity = minimum_quantity
        self.estimated_km_per_month = estimated_km_per_month


class DummyTender:
    def __init__(self):
        self.bid_id = "BID-2026-001"
        self.dates = DummyDates(
            contract_period="2 Year(s)",
            duration_months=24,
            submission_deadline="2026-10-01",
            opening_date="2026-10-02",
        )
        self.financials = DummyFinancials(estimated_bid_value=1500000, emd_amount=15000)
        self.fleet = DummyFleet(
            vehicle_type="32-Seater Bus",
            minimum_quantity=10,
            estimated_km_per_month=2500,
        )


def test_format_tender_metadata_happy_path():
    # Arrange
    tender_obj = DummyTender()

    # Act
    result = format_tender_metadata(tender_obj)

    # Assert
    assert "- Bid ID: BID-2026-001" in result
    assert "- Contract Period / Duration: 2 Year(s) (24 Months)" in result
    assert "- Bid End / Submission Date: 2026-10-01" in result
    assert "- Opening Date: 2026-10-02" in result
    assert "- Estimated Bid Value: 1500000" in result
    assert "- EMD Amount: 15000" in result
    assert "- Vehicle Type: 32-Seater Bus" in result
    assert "- Quantity: 10" in result
    assert "- Estimated Monthly KM: 2500 KM" in result


def test_format_tender_metadata_supports_json_dict():
    tender_obj = {
        "bid_id": "BID-2026-001",
        "dates": {
            "contract_period": "2 Year(s)",
            "duration_months": 24,
            "submission_deadline": "2026-10-01",
            "opening_date": "2026-10-02",
        },
        "financials": {
            "estimated_bid_value": 1500000,
            "emd_amount": 15000,
        },
        "fleet": {
            "vehicle_type": "32-Seater Bus",
            "minimum_quantity": 10,
            "estimated_km_per_month": 2500,
            "max_vehicle_age_years": None,
            "ownership_required": None,
            "scope_of_work": None,
        },
        "eligibility": {
            "work_experience_years": None,
            "experience_calculation_method": None,
            "minimum_experience_value_lakhs": None,
            "gst_required": None,
            "gst_conditions": None,
            "bid_type": None,
            "working_capital_minimum_lakhs": None,
            "jv_allowed": None,
            "jv_minimum_cost_crores": None,
        },
        "documents": [],
        "compliance": {
            "written_consent_regarding_arbitration": None,
            "integrity_pact": None,
            "code_of_integrity_for_public_procurement": None,
            "restrictions_on_procurement_from_certain_countries": None,
            "undertaking_for_genuineness_of_information": None,
        },
    }

    result = format_tender_metadata(tender_obj)

    assert "- Bid ID: BID-2026-001" in result
    assert "- Contract Period / Duration: 2 Year(s) (24 Months)" in result
    assert "- Bid End / Submission Date: 2026-10-01" in result
    assert "- Opening Date: 2026-10-02" in result
    assert "- Estimated Bid Value: 1500000" in result
    assert "- EMD Amount: 15000" in result
    assert "- Vehicle Type: 32-Seater Bus" in result
    assert "- Quantity: 10" in result
    assert "- Estimated Monthly KM: 2500 KM" in result
    assert "N/A" not in result


def test_format_tender_metadata_returns_fallback_for_none():
    # Arrange
    tender_obj = None

    # Act
    result = format_tender_metadata(tender_obj)

    # Assert
    assert result == "No structured metadata available."


def test_format_tender_metadata_handles_missing_or_none_nested_attributes():
    # Arrange
    class PartialFinancials:
        estimated_bid_value = None
        emd_amount = None

    class PartialFleet:
        vehicle_type = None
        minimum_quantity = None
        estimated_km_per_month = None

    class PartialTender:
        bid_id = "BID-2026-002"
        dates = None
        financials = PartialFinancials()
        fleet = PartialFleet()

    # Act
    result = format_tender_metadata(PartialTender())

    # Assert
    assert "- Bid ID: BID-2026-002" in result
    assert "- Contract Period / Duration: N/A (N/A Months)" in result
    assert "- Bid End / Submission Date: N/A" in result
    assert "- Opening Date: N/A" in result
    assert "- Estimated Bid Value: N/A" in result
    assert "- EMD Amount: N/A" in result
    assert "- Vehicle Type: N/A" in result
    assert "- Quantity: N/A" in result
    assert "- Estimated Monthly KM: N/A KM" in result


def test_build_rag_chain_returns_runnable(monkeypatch):
    monkeypatch.setattr(tender_rag, "get_ensemble_retriever", lambda **kwargs: object())
    monkeypatch.setattr(tender_rag, "get_llm", lambda: object())
    monkeypatch.setattr(
        tender_rag,
        "build_multi_query_retrieval_chain",
        lambda retriever, llm, stage_latencies_ms=None: object(),
    )

    result = tender_rag.build_rag_chain(tender_id="tender-1", chunk=[])

    assert isinstance(result, Runnable)


def test_multi_query_chain_records_expansion_and_retrieval_latencies():
    document = Document(page_content="Tender document", metadata={})

    class FakeRetriever:
        def batch(self, queries):
            assert queries == ["What is the deadline?", "deadline query"]
            return [[document], [document]]

    stage_latencies_ms = {}
    chain = build_multi_query_retrieval_chain(
        FakeRetriever(),
        RunnableLambda(lambda prompt: "deadline query"),
        stage_latencies_ms,
    )

    result = chain.invoke("What is the deadline?")

    assert result == [document]
    assert stage_latencies_ms["query_expansion_ms"] >= 0
    assert stage_latencies_ms["retrieval_ms"] >= 0
    