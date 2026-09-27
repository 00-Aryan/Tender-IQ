import pymupdf4llm
# from pathlib import Path
import fitz


def load_tender_pdf(file_path: str) -> str:
    result = pymupdf4llm.to_markdown(
        doc=str(file_path),
        page_chunks=True,
    )
    
    pages = []
    for page in result:
        page_num = page["metadata"]["page_number"]
        page_text = page["text"]
        # Prepend the unambiguous boundary anchor
        pages.append(f"\n<!-- PAGE_{page_num} -->\n{page_text}")

    return "\n".join(pages)

def load_pdf_text(file_path: str, max_pages: int = 6) -> str:
    with fitz.open(file_path) as doc:
        pages = [page.get_text() for page in doc[:max_pages]]
    return "\n".join(pages)


# load_tender_pdf("data/tenders/31-mAY/chandwa/add tnC.pdf")

# if __name__ == "__main__":
#     load_tender_pdf("/mnt/c/Users/Aryan/Downloads/tender/GeM-Bidding-9881703.pdf")