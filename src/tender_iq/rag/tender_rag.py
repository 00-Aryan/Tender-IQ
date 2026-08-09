from langchain_core.runnables import RunnableParallel , RunnablePassthrough , RunnableLambda
from langchain_core.output_parsers import StrOutputParser
from tender_iq.vector_store.chroma_store import get_retriever
from tender_iq.prompts.rag_prompt import rag_prompt
from tender_iq.config.llm_config import get_llm

def format_docs(retrieved_doc):
    formatted = []
    for doc in retrieved_doc:
        section = doc.metadata.get("subsection") or doc.metadata.get("section") or "Unknown Section"
        formatted.append(f"[Source: {section}]\n{doc.page_content}")
    return "\n\n".join(formatted)


def build_rag_chain(tender_id: str):
    retriever = get_retriever(tender_id=tender_id)
    llm = get_llm()
    parser = StrOutputParser()
    chain = ( 
        RunnableParallel({
            "context" : retriever | RunnableLambda(format_docs),
            'question': RunnablePassthrough()
            })
            | rag_prompt
            |  llm
            | parser
    )
    return chain

chain = build_rag_chain("test_001")
result = chain.invoke("What is the EMD amount?")
print(result)