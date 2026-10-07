import pymupdf4llm
from langchain_core.documents import Document

from tender_iq.document_processor.loader import load_tender_pdf


def test_load_tender_pdf_returns_page_documents_with_one_indexed_metadata(monkeypatch):
    # Arrange
    fake_pages = [
        {"metadata": {"page_number": 1}, "text": "Page 1 content"},
        {"metadata": {}, "text": "Page 2 content"},
    ]

    def fake_to_markdown(doc, page_chunks):
        assert doc == "/tmp/sample.pdf"
        assert page_chunks is True
        return fake_pages

    monkeypatch.setattr(pymupdf4llm, "to_markdown", fake_to_markdown)

    # Act
    result = load_tender_pdf("/tmp/sample.pdf")

    # Assert
    assert result == [
        Document(page_content="Page 1 content", metadata={"page_number": 1}),
        Document(page_content="Page 2 content", metadata={"page_number": 2}),
    ]
