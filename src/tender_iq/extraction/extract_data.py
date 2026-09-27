from pathlib import Path
from typing import Any, Dict

from tender_iq.document_processor.loader import load_pdf_text
from tender_iq.models.tender_requirements import (
    Dates,
    EligibilityCriteria,
    FleetSpecification,
    LegalCompliance,
    TenderFinancials,
    TenderRequirements,
)
from tender_iq.parser.reg_ex_parser import parse_with_regex




def build_tender_requirements(raw: Dict[str, Any]) -> TenderRequirements:
    """Maps the raw extracted dictionary into the structured Pydantic schema."""
    return TenderRequirements(
        bid_id=raw.get("bid_id"),
        financials=TenderFinancials(
            emd_amount=raw.get("emd_amount"),
            estimated_bid_value=raw.get("estimated_bid_value"),
        ),
        eligibility=EligibilityCriteria(
            bid_type=raw.get("bid_type"),
        ),
        fleet=FleetSpecification(
            vehicle_type=raw.get("vehicle_type"),
            estimated_km_per_month=raw.get("estimated_km"),
        ),
        dates=Dates(
            submission_deadline=raw.get("submission_deadline"),
            opening_date=raw.get("opening_date"),
            contract_period=raw.get("contract_period"),
            duration_months=raw.get("duration_months"),
        ),
        compliance=LegalCompliance(),
        documents=[],
    )


def validate_extraction_completeness(tender: TenderRequirements) -> bool:
    """Evaluates whether critical fields are populated to decide Tier 2 routing."""
    critical_checks = [
        tender.bid_id is not None,
        tender.dates.submission_deadline is not None,
        tender.dates.opening_date is not None,
        tender.fleet.vehicle_type is not None,
        tender.fleet.estimated_km_per_month is not None,
    ]
    return all(critical_checks)


def process_tender_pdf(pdf_path: str, max_pages: int = 6) -> TenderRequirements:
    """Public orchestration interface."""
    raw_text = load_pdf_text(pdf_path, max_pages=max_pages)
    regex_dict = parse_with_regex(raw_text)
    tender_data = build_tender_requirements(regex_dict)

    if not validate_extraction_completeness(tender_data):
        print(f"[FALLBACK NEEDED] Missing critical fields for {Path(pdf_path).name}. Routing to LLM...")
        # tender_data = parse_with_llm(raw_text, tender_data)

    return tender_data