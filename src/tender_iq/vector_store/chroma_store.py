from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document



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

def get_retriever(tender_id: str, k: int = 4):

    # load existing ChromaDB
    vector_store = get_vector_store() 

    # return MMR retriever filtered by tender_id
    retriever = vector_store.as_retriever(
        search_type="mmr",
        search_kwargs = {"k": k,"filter": {"tender_id": tender_id} }
    )
    return retriever