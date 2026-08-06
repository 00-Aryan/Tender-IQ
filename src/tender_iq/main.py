import uuid

from tender_iq.document_processor.loader import load_tender_pdf
from tender_iq.document_processor.metadata_extractor import extract_tender_id
from tender_iq.document_processor.chunker import chunk_tender_documents
from tender_iq.vector_store.chroma_store import store_tender


def main(pdf_path: str):
    markdown = load_tender_pdf(pdf_path)

    tender_id = extract_tender_id(markdown)
    if tender_id is None:
        tender_id = str(uuid.uuid4())

    chunks = chunk_tender_documents(markdown)

    store_tender(chunks, tender_id)


if __name__ == "__main__":
    pdf_path = "data/tenders/31-mAY/chandwa/add tnC.pdf"
    main(pdf_path)