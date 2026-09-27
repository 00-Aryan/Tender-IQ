import re

from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

HEADERS_TO_SPLIT_ON = [
    ("#", "section"),
    ("##", "subsection"),
    ("###", "clause")
]

PAGE_REGEX = re.compile(r"<!-- PAGE_(\d+) -->")


def _split_document_by_page_markers(doc: Document) -> list[Document]:
    matches = list(PAGE_REGEX.finditer(doc.page_content))
    if not matches:
        return [doc]

    split_docs: list[Document] = []
    current_page = doc.metadata.get("page_number", 1)
    cursor = 0

    for match in matches:
        prefix = doc.page_content[cursor:match.start()]
        if prefix.strip():
            metadata = dict(doc.metadata)
            metadata["page_number"] = current_page
            split_docs.append(Document(page_content=prefix.strip(), metadata=metadata))

        current_page = int(match.group(1))
        cursor = match.end()

    suffix = doc.page_content[cursor:]
    if suffix.strip():
        metadata = dict(doc.metadata)
        metadata["page_number"] = current_page
        split_docs.append(Document(page_content=suffix.strip(), metadata=metadata))

    return split_docs


def chunk_tender_documents(markdown_text: str) -> list:
    if not markdown_text:
        return []

    markdown_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=HEADERS_TO_SPLIT_ON,
        strip_headers=False,
    )
    md_header_splits = markdown_splitter.split_text(markdown_text)

    chunk_size = 1200
    chunk_overlap = 100
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", " ", ""],
    )

    splits = text_splitter.split_documents(md_header_splits)
    page_split_documents: list[Document] = []

    for doc in splits:
        page_split_documents.extend(_split_document_by_page_markers(doc))

    return page_split_documents