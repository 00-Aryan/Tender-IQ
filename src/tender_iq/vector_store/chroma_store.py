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

    # add tender_id to each chunk's metadata
    for chunk in chunks:
        chunk.metadata["tender_id"] = tender_id
        # chunk.metadata["source_file"] = filename

    #open the vector store 
    vector_store = get_vector_store()

    #add the chunk to vector store 
    vector_store.add_documents(chunks)

    # return number of chunks stored
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

    # Equalize weights so BM25 exact keyword hits aren't drowned out
    return EnsembleRetriever(
        retrievers=[bm25_retriever, vector_retriever],
        weights=[0.4, 0.6]
    )