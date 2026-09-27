import re 
from datetime import datetime
from typing import Any, Dict

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