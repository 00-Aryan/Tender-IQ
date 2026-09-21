import fitz 
import re 
from datetime import datetime
from typing import Dict, Any
from pathlib import Path

from tender_iq.models.tender_requirements import (
    TenderRequirements,
    TenderFinancials,
    FleetSpecification,
    EligibilityCriteria,
    Dates,
    LegalCompliance
)

def extract_tender_data(file_path:str, max_pages:int = 6):

    with fitz.open(file_path) as doc:
        pages = [page.get_text() for page in doc[:max_pages]]
    return "\n".join(pages)

def parse_with_regex(text: str) -> Dict[str, Any]:
    extracted: Dict[str, Any] = {
        "bid_id": None,
        "submission_deadline": None,
        "opening_date": None,
        "estimated_bid_value": None,
        "contract_period":None,
        "emd_amount": None,
        "bid_type": None,
        "vehicle_type": None,
        "estimated_km": None,
        "duration_months": None,
    }

    # 1. Bid ID
    bid_match = re.search(r"Bid Number:\s*([\w/-]+)", text)
    if bid_match:
        extracted["bid_id"] = bid_match.group(1).strip()

    # 2. Submission Deadline
    end_date_match = re.search(r"Bid End Date/Time\s*[:\n]\s*(\d{2}-\d{2}-\d{4})", text)
    if end_date_match:
        extracted["submission_deadline"] = datetime.strptime(end_date_match.group(1), "%d-%m-%Y").date()

    # 3. Opening Date
    open_date_match = re.search(r"Bid Opening\s+Date/Time\s*[:\n]\s*(\d{2}-\d{2}-\d{4})", text)
    if open_date_match:
        extracted["opening_date"] = datetime.strptime(open_date_match.group(1), "%d-%m-%Y").date()

    # 10.contract period 
    contract_period_match = re.search(r"Contract Period[^\n]*\n\s*([^\n]+)", text)
    if contract_period_match:
        extracted["contract_period"] = contract_period_match.group(1).strip()

    # 4. Estimated Bid Value
    val_match = re.search(
        r"Estimated Bid Value[^\d\n]*\n(?:[^\d\n]*\n){0,3}\s*([\d,]+(?:\.\d+)?)",
        text,
        re.IGNORECASE
    )
    if val_match:
        try:
            # Strip commas before converting to float
            clean_num = val_match.group(1).replace(",", "")
            extracted["estimated_bid_value"] = float(clean_num)
        except ValueError:
            pass
    # 5. EMD Amount needs to check edge case 
    emd_match = re.search(r"EMD Amount[^\n]*\n\s*([\d.]+)", text)
    if emd_match:
        try:
            extracted["emd_amount"] = float(emd_match.group(1))
        except ValueError:
            pass
    
    # 6. Type of Bid needs to check edge case 
    bid_type_match = re.search(r"Type of Bid\s*\n\s*([^\n]+)", text)
    if bid_type_match:
        extracted["bid_type"] = bid_type_match.group(1).strip()

    # 7. Vehicle Type needs to check edge case 
    vehicle_match = re.search(r"Vehicle Type\s*\n\s*([^\n]+)", text)
    if vehicle_match:
        extracted["vehicle_type"] = vehicle_match.group(1).strip()

    # 8. Estimated KM monthly (Target: 4200)
    estimated_run_match = re.search(r"Estimated KMs.*?:\s*(\d+)", text, re.DOTALL | re.IGNORECASE)
    if estimated_run_match:
        try:
            extracted["estimated_km"] = int(estimated_run_match.group(1))
        except ValueError:
            pass

    # 9. Duration in months (Target: 24)
    duration_match = re.search(r"Duration in Months.*?:\s*(\d+)", text, re.DOTALL | re.IGNORECASE)
    if duration_match:
        try:
            extracted["duration_months"] = int(duration_match.group(1))
        except ValueError:
            pass
    
    return extracted

def build_tender_requirements(raw: dict) -> TenderRequirements:
    """Instantiates and type-validates the Pydantic model from regex output."""
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
    """
    Checks if critical fields are present.
    Returns True if regex was sufficient, False if LLM fallback is needed.
    """
    critical_checks = [
        tender.bid_id is not None,
        tender.dates.submission_deadline is not None,
        tender.dates.opening_date is not None,
        tender.fleet.vehicle_type is not None,
        tender.fleet.estimated_km_per_month is not None,
    ]
    return all(critical_checks)


def process_tender_pdf(pdf_path: str) -> TenderRequirements:
    raw_text = extract_tender_data(pdf_path)
    regex_dict = parse_with_regex(raw_text)
    
    # 1. Schema Validation (Pydantic will raise ValidationError if types are corrupt)
    tender_data = build_tender_requirements(regex_dict)
    
    # 2. Gatekeeper Check
    if not validate_extraction_completeness(tender_data):
        print(f"[FALLBACK NEEDED] Incomplete regex extraction for {pdf_path}. Escalating to LLM...")
        # tender_data = parse_with_llm(raw_text, tender_data)
    
    return tender_data
    
if __name__ == "__main__":
    tender_dir = Path("/mnt/c/Users/Aryan/Downloads/tender")
    
    # Grab all .pdf files (case-insensitive check if needed)
    pdf_files = sorted(tender_dir.glob("*.pdf"))

    print(f"Found {len(pdf_files)} tenders to parse.\n")

    for pdf_path in pdf_files:
        print(f"{'='*20} {pdf_path.name} {'='*20}")
        try:
            raw_text = extract_tender_data(str(pdf_path))
            result = parse_with_regex(raw_text)

            for key, val in result.items():
                print(f"  {key}: {val} (type: {type(val).__name__})")
        except Exception as e:
            print(f"  [ERROR] Failed to parse {pdf_path.name}: {e}")
        
        print()