"""
Chat service layer.
Coordinates SQLite, ChromaDB, and your existing LangChain RAG chain.
"""
from sqlalchemy.orm import Session
from langchain_core.documents import Document

from tender_iq.db.session import SessionLocal
from tender_iq.crud.tenders import get_tender_by_id
from tender_iq.vector_store.chroma_store import get_vector_store
from tender_iq.rag.tender_rag import build_rag_chain
from tender_iq.api.schemas.chat import ChatResponse, CitationSource


def _is_basic_greeting(query: str) -> bool:
    """Return True for simple conversational greetings and polite chitchat."""
    if not query:
        return False

    normalized = " ".join(query.strip().lower().split())
    greeting_set = {
        "hi",
        "hello",
        "hey",
        "greetings",
        "thanks",
        "thank you",
        "thankyou",
        "good morning",
        "good afternoon",
        "good evening",
    }

    if normalized in greeting_set:
        return True

    for prefix in (
        "hi ",
        "hello ",
        "hey ",
        "greetings ",
        "thanks ",
        "thank you ",
        "thankyou ",
    ):
        if normalized.startswith(prefix):
            return True

    return False


def get_all_chunks_for_tender(tender_id: str) -> list[Document]:
    """
    Reconstructs the chunks list from ChromaDB for BM25/Ensemble retrieval,
    matching how Streamlit used to pass them in memory.
    """
    vector_store = get_vector_store()
    # Query ChromaDB's underlying collection using the metadata filter
    results = vector_store._collection.get(
        where={"tender_id": tender_id},
        include=["documents", "metadatas"]
    )
    
    docs = []
    contents = results.get("documents", [])
    metadatas = results.get("metadatas", [])
    
    for content, meta in zip(contents, metadatas):
        docs.append(Document(page_content=content, metadata=meta))
        
    return docs

def process_chat_query(db: Session, tender_id: str, query: str) -> ChatResponse:
    """
    Executes the full RAG pipeline and maps the output to your ChatResponse schema.
    """
    normalized_query = " ".join(query.strip().lower().split())

    if _is_basic_greeting(normalized_query):
        return ChatResponse(
            tender_id=tender_id,
            answer="Hello! I am your TenderIQ assistant. How can I help you analyze this tender document today?",
            citations=[]
        )

    # 1. Fetch structured regex specs from SQLite
    db_tender = get_tender_by_id(db, tender_id)
    if not db_tender:
        raise ValueError(f"Tender ID '{tender_id}' not found in database.")
    
    tender_specs = db_tender.specs

    # 2. Fetch all chunks from ChromaDB for this tender 
    # (Enabling your BM25 + Vector Ensemble Retriever to work perfectly)
    chunks = get_all_chunks_for_tender(tender_id)
    if not chunks:
        raise ValueError(f"No vector documents found in ChromaDB for tender '{tender_id}'.")

    # 3. Build the RAG chain and retain the documents used for the answer
    rag_chain = build_rag_chain(tender_id=tender_id, chunk=chunks, tender_obj=tender_specs)

    # 4. Invoke the chain with the user's query
    rag_result = rag_chain.invoke(query)
    answer = rag_result["answer"]

    # 5. Cite the same documents that supplied the answer context
    citations = []
    for chunk in rag_result["sources"][:3]:
        meta = chunk.metadata
        citations.append(
            CitationSource(
                page_number=meta.get("page_number"),
                section=meta.get("subsection") or meta.get("section"),
                snippet=chunk.page_content[:250] + "..."
            )
        )

    return ChatResponse(
        tender_id=tender_id,
        answer=answer,
        citations=citations
    )