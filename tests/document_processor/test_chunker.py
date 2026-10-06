from tender_iq.document_processor.chunker import chunk_tender_documents


def test_chunk_tender_documents_preserves_header_metadata():
    # Arrange
    markdown_text = """# Transport Services
## Fleet Requirement
### Bus Category
Ten buses are required for urban routes.
## Planning Details
### Route Compliance
Vehicle assignment will be verified on the route map.
"""

    # Act
    chunks = chunk_tender_documents(markdown_text)

    # Assert
    assert any(doc.metadata.get("section") == "Transport Services" for doc in chunks)
    assert any(doc.metadata.get("subsection") == "Fleet Requirement" for doc in chunks)
    assert any(doc.metadata.get("clause") == "Bus Category" for doc in chunks)
    assert any(doc.metadata.get("clause") == "Route Compliance" for doc in chunks)


def test_chunk_tender_documents_detects_page_markers():
    # Arrange
    markdown_text = """# Tender Overview
<!-- PAGE_1 -->
Page 1 content starts here.

<!-- PAGE_2 -->
Page 2 content starts here.
"""

    # Act
    chunks = chunk_tender_documents(markdown_text)
    page_numbers = [doc.metadata.get("page_number") for doc in chunks if doc.metadata.get("page_number") is not None]

    # Assert
    assert 1 in page_numbers
    assert 2 in page_numbers
    assert all(isinstance(page_number, int) for page_number in page_numbers)


def test_chunk_tender_documents_returns_empty_list_for_empty_input():
    # Arrange
    markdown_text = ""

    # Act
    result = chunk_tender_documents(markdown_text)

    # Assert
    assert result == []
