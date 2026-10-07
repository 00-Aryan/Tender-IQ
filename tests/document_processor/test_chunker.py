from langchain_core.documents import Document

from tender_iq.document_processor.chunker import chunk_tender_documents


def test_chunk_tender_documents_preserves_header_metadata():
    # Arrange
    pages = [
        Document(
            page_content="""# Transport Services
## Fleet Requirement
### Bus Category
Ten buses are required for urban routes.
## Planning Details
### Route Compliance
Vehicle assignment will be verified on the route map.
""",
            metadata={"page_number": 1},
        )
    ]

    # Act
    chunks = chunk_tender_documents(pages)

    # Assert
    assert any(doc.metadata.get("section") == "Transport Services" for doc in chunks)
    assert any(doc.metadata.get("subsection") == "Fleet Requirement" for doc in chunks)
    assert any(doc.metadata.get("clause") == "Bus Category" for doc in chunks)
    assert any(doc.metadata.get("clause") == "Route Compliance" for doc in chunks)


def test_chunk_tender_documents_preserves_page_metadata_on_child_chunks():
    # Arrange
    pages = [
        Document(
            page_content="# Tender Overview\n" + "Page 1 content starts here. " * 100,
            metadata={"page_number": 1},
        ),
        Document(
            page_content="# Tender Details\n" + "Page 2 content starts here. " * 100,
            metadata={"page_number": 2},
        ),
    ]

    # Act
    chunks = chunk_tender_documents(pages)

    # Assert
    assert len(chunks) > len(pages)
    assert all("page_number" in doc.metadata for doc in chunks)
    assert {doc.metadata["page_number"] for doc in chunks} == {1, 2}
    assert all(
        doc.metadata["page_number"] == 1
        for doc in chunks
        if "Page 1 content" in doc.page_content
    )
    assert all(
        doc.metadata["page_number"] == 2
        for doc in chunks
        if "Page 2 content" in doc.page_content
    )


def test_chunk_tender_documents_returns_empty_list_for_empty_input():
    # Arrange
    pages = []

    # Act
    result = chunk_tender_documents(pages)

    # Assert
    assert result == []
