import pymupdf4llm
import fitz
from langchain_core.documents import Document


def load_tender_pdf(file_path: str) -> list[Document]:
    result = pymupdf4llm.to_markdown(
        doc=str(file_path),
        page_chunks=True,
    )

    return [
        Document(
            page_content=page["text"],
            metadata={"page_number": page["metadata"].get("page_number", idx)},
        )
        for idx, page in enumerate(result, start=1)
    ]

def load_pdf_text(file_path: str, max_pages: int = 6) -> str:
    with fitz.open(file_path) as doc:
        pages = [page.get_text() for page in doc[:max_pages]]
    return "\n".join(pages)
