from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

HEADERS_TO_SPLIT_ON = [
    ("#", "section"),
    ("##", "subsection"),
    ("###", "clause")
]


def chunk_tender_documents(pages: list[Document]) -> list[Document]:
    if not pages:
        return []

    markdown_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=HEADERS_TO_SPLIT_ON,
        strip_headers=False,
    )
    md_header_splits = [
        Document(
            page_content=split.page_content,
            metadata={**page.metadata, **split.metadata},
        )
        for page in pages
        for split in markdown_splitter.split_text(page.page_content)
    ]

    chunk_size = 1200
    chunk_overlap = 100
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", " ", ""],
    )

    return text_splitter.split_documents(md_header_splits)