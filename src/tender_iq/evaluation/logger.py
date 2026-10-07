import csv
from datetime import datetime
from pathlib import Path

LOG_FILE = Path("data/eval_history.csv")

def log_eval_run(
    run_tag: str,
    tender_id: str,
    test_size: int,
    faithfulness: float,
    answer_relevancy: float,
    context_precision: float,
    avg_total_latency_ms: float,
    notes: str = ""
):
    """Appends an evaluation run record to a local CSV history file for regression tracking."""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    file_exists = LOG_FILE.is_file()
    
    fields = [
        "timestamp", "run_tag", "tender_id", "test_size",
        "faithfulness", "answer_relevancy", "context_precision",
        "avg_total_latency_ms", "notes"
    ]
    
    with open(LOG_FILE, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        if not file_exists:
            writer.writeheader()
            
        writer.writerow({
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "run_tag": run_tag,
            "tender_id": tender_id,
            "test_size": test_size,
            "faithfulness": round(faithfulness, 3),
            "answer_relevancy": round(answer_relevancy, 3),
            "context_precision": round(context_precision, 3),
            "avg_total_latency_ms": round(avg_total_latency_ms, 2),
            "notes": notes
        })
    print(f"Logged evaluation run '{run_tag}' to {LOG_FILE}")