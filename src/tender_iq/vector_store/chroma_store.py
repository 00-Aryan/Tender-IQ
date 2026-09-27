from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document
from langchain_community.retrievers import BM25Retriever
from langchain_classic.retrievers import EnsembleRetriever




CHROMA_PATH = "data/chroma"
COLLECTION_NAME = "tender_iq"

# Module level — just a placeholder, no model loaded yet
_embed_model = None

def get_embed_model():
    global _embed_model
    if _embed_model is None:
        # Only runs first time — subsequent calls return cached model
        _embed_model = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    return _embed_model

def get_vector_store():
    return Chroma(
    collection_name=COLLECTION_NAME,
    persist_directory=CHROMA_PATH,
    embedding_function=get_embed_model(),
    )

def store_tender(chunks: list[Document], tender_id: str) -> int:
    vector_store = get_vector_store()

    # 1. Clean Sweep: Purge any existing chunks for this tender_id
    try:
        vector_store._collection.delete(where={"tender_id": tender_id})
    except Exception:
        # If the collection is brand new or tender doesn't exist yet, continue safely
        pass

    # 2. Attach metadata and prepare IDs
    for chunk in chunks:
        chunk.metadata["tender_id"] = tender_id

    ids = [f"{tender_id}_{i}" for i in range(len(chunks))]

    # 3. Add clean documents with deterministic IDs
    vector_store.add_documents(documents=chunks, ids=ids)

    return len(chunks)

def get_retriever(tender_id: str, k: int = 6):
    vector_store = get_vector_store() 

    # Option A: Pure similarity search 
    # return vector_store.as_retriever(
    #     search_type="similarity",
    #     search_kwargs={"k": k, "filter": {"tender_id": tender_id}}
    # )

    # Option B: High-relevance MMR 
    return vector_store.as_retriever(
        search_type="mmr",
        search_kwargs={
            "k": k,
            "fetch_k": 20,
            "lambda_mult": 0.85, # 85% similarity preference
            "filter": {"tender_id": tender_id}
        }
    )

def get_ensemble_retriever(chunks: list, tender_id: str, k: int = 6):
    bm25_retriever = BM25Retriever.from_documents(chunks)
    bm25_retriever.k = k

    vector_retriever = get_retriever(tender_id=tender_id, k=k)

    
    return EnsembleRetriever(
        retrievers=[bm25_retriever, vector_retriever],
        weights=[0.4, 0.6]
    )