from langchain_text_splitters import MarkdownHeaderTextSplitter
from langchain_text_splitters import RecursiveCharacterTextSplitter

HEADERS_TO_SPLIT_ON = [
    ("#", "section"),
    ("##", "subsection"), 
    ("###", "clause")
]

def chunk_tender_documents(markdown_text: str) -> list:
    # Step 1: split by markdown headers
    markdown_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=HEADERS_TO_SPLIT_ON,
        strip_headers=False
        )
    
    md_header_splits = markdown_splitter.split_text(markdown_text)

    # Step 2: split oversized sections into smaller character-based chunks
    chunk_size = 1000
    chunk_overlap = 100
    text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=chunk_size, chunk_overlap=chunk_overlap
    )

    # Step 3: return list of Documents with metadata intact
    splits = text_splitter.split_documents(md_header_splits)
    
    return splits