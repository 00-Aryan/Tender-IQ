import re

def extract_tender_id(markdown: str) -> str | None:
    pattern = r"Bid Number\s*:\s*(GEM/\d{4}/B/\d+)"
    match = re.search(pattern, markdown)

    if match:
        return match.group(1)

    return None