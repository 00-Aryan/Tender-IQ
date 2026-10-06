import pymupdf4llm

from tender_iq.document_processor.loader import load_tender_pdf


def test_load_tender_pdf_inserts_page_markers(monkeypatch):
    # Arrange
    fake_pages = [
        {"metadata": {"page_number": 1}, "text": "Page 1 content"},
        {"metadata": {"page_number": 2}, "text": "Page 2 content"},
    ]

    def fake_to_markdown(doc, page_chunks):
        assert doc == "/tmp/sample.pdf"
        assert page_chunks is True
        return fake_pages

    monkeypatch.setattr(pymupdf4llm, "to_markdown", fake_to_markdown)

    # Act
    result = load_tender_pdf("/tmp/sample.pdf")

    # Assert
    assert "<!-- PAGE_1 -->" in result
    assert "Page 1 content" in result
    assert "<!-- PAGE_2 -->" in result
    assert "Page 2 content" in result
