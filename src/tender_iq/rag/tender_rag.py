from langchain_core.runnables import RunnableParallel, RunnablePassthrough, RunnableLambda
from langchain_core.output_parsers import StrOutputParser
from tender_iq.vector_store.chroma_store import get_ensemble_retriever
from tender_iq.prompts.rag_prompt import rag_prompt
from tender_iq.config.llm_config import get_llm
from tender_iq.rag.query_transformers import build_multi_query_retrieval_chain

def format_docs(retrieved_doc):
    formatted = []
    for doc in retrieved_doc:
        section = doc.metadata.get("subsection") or doc.metadata.get("section") or "Unknown Section"
        formatted.append(f"[Source: {section}]\n{doc.page_content}")
    return "\n\n".join(formatted)

def build_rag_chain(tender_id: str, chunk: list):
    
    retriever = get_ensemble_retriever(tender_id=tender_id, chunks=chunk)
    llm = get_llm()
    parser = StrOutputParser()

    retrieval_chain = build_multi_query_retrieval_chain(retriever, llm)

    chain = ( 
        RunnableParallel({
            "context": retrieval_chain | RunnableLambda(format_docs),
            'question': RunnablePassthrough()
        })
        | rag_prompt
        | llm
        | parser
    )
    return chain
