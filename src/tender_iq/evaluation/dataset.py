"""Shared reader for the single reviewed evaluation dataset."""

import hashlib
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
EVALUATION_DIR = Path(__file__).parent
DATASET = EVALUATION_DIR / "dataset_v1.json"


def load_dataset(path=DATASET):
    """Input: a versioned question file. Output: validated data and its SHA-256.

    Only reviewed cases belong here. Historical answers and labels are not dataset
    fields. A changed dataset needs a new capture; old answers cannot silently use
    new references. Both capture and scoring use this reader.
    """
    raw = path.read_bytes()
    data = json.loads(raw)
    if data["schema_version"] != 1 or not data["dataset_version"]:
        raise ValueError("Unsupported or missing dataset version.")
    if not data["documents"] or not data["cases"]:
        raise ValueError("Dataset must contain documents and reviewed cases.")
    for tender_id, document in data["documents"].items():
        if not tender_id or not document["pdf_path"] or len(document["sha256"]) != 64:
            raise ValueError("Each document needs an identity, PDF path and SHA-256.")
    seen = set()
    for case in data["cases"]:
        if set(case) != {"id", "tender_id", "question", "expected_answer", "answerable", "evidence"}:
            raise ValueError("Case fields must match the minimal dataset schema; remove old aliases, hints or review labels.")
        for field in ("id", "tender_id", "question", "expected_answer"):
            if not isinstance(case[field], str) or not case[field].strip():
                raise ValueError(f"Each case needs a nonblank {field}.")
        if case["id"] in seen:
            raise ValueError("Question IDs must be unique.")
        seen.add(case["id"])
        if case["tender_id"] not in data["documents"] or type(case["answerable"]) is not bool:
            raise ValueError("Case document identity or answerable flag is invalid.")
        if not case["evidence"] or any(type(e["page"]) is not int or e["page"] < 1 for e in case["evidence"]):
            raise ValueError("Reviewed cases need one-based physical evidence pages.")
    return data, hashlib.sha256(raw).hexdigest()
