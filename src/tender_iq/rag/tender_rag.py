from langchain_core.runnables import RunnableParallel, RunnablePassthrough, RunnableLambda
from langchain_core.output_parsers import StrOutputParser
from tender_iq.vector_store.chroma_store import get_ensemble_retriever
from tender_iq.prompts.rag_prompt import rag_prompt
from tender_iq.config.llm_config import get_llm
from tender_iq.rag.query_transformers import build_multi_query_retrieval_chain

def format_docs(retrieved_docs):
    formatted = []
    for doc in retrieved_docs:
        page = doc.metadata.get("page_number") 
        section = doc.metadata.get("subsection") or doc.metadata.get("section")

        header_parts = []
        if page and str(page).lower() != "n/a":
            header_parts.append(f"Page {page}")
        if section and section != "Unknown Section":
            header_parts.append(f"Section: {section}")

        header_str = " | ".join(header_parts) if header_parts else "Tender Document"
        formatted.append(f"[{header_str}]\n{doc.page_content}")
        
    return "\n\n---\n\n".join(formatted)

def format_tender_metadata(tender_obj) -> str:
    if not tender_obj:
        return "No structured metadata available."

    def safe_value(obj, attr, default="N/A"):
        value = getattr(obj, attr, default)
        return default if value is None else value

    dates = getattr(tender_obj, 'dates', None)
    financials = getattr(tender_obj, 'financials', None)
    fleet = getattr(tender_obj, 'fleet', None)

    lines = [
        f"- Bid ID: {safe_value(tender_obj, 'bid_id')}",
        f"- Contract Period / Duration: {safe_value(dates, 'contract_period')} "
        f"({safe_value(dates, 'duration_months')} Months)",
        f"- Bid End / Submission Date: {safe_value(dates, 'submission_deadline')}",
        f"- Opening Date: {safe_value(dates, 'opening_date')}",
        f"- Estimated Bid Value: {safe_value(financials, 'estimated_bid_value')}",
        f"- EMD Amount: {safe_value(financials, 'emd_amount')}",
        f"- Vehicle Type: {safe_value(fleet, 'vehicle_type')}",
        f"- Quantity: {safe_value(fleet, 'quantity')}",
        f"- Estimated Monthly KM: {safe_value(fleet, 'estimated_km_per_month')} KM",
    ]
    return "\n".join(lines)




def build_rag_chain(tender_id: str, chunk: list , tender_obj=None):
    
    retriever = get_ensemble_retriever(tender_id=tender_id, chunks=chunk)
    llm = get_llm()
    parser = StrOutputParser()

    retrieval_chain = build_multi_query_retrieval_chain(retriever, llm)


    # 1. Format metadata and partially bind to prompt upfront
    metadata_str = format_tender_metadata(tender_obj)
    configured_prompt = rag_prompt.partial(metadata_specs=metadata_str)

    chain = ( 
        RunnableParallel({
            "context": retrieval_chain | RunnableLambda(format_docs),
            'question': RunnablePassthrough()
        })
        | configured_prompt
        | llm
        | parser
    )
    return chain
