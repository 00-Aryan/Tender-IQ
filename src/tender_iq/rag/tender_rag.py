import hashlib
import json
import logging
import time

from langchain_core.runnables import RunnableLambda
from langchain_core.output_parsers import StrOutputParser
from tender_iq.vector_store.chroma_store import get_ensemble_retriever
from tender_iq.prompts.rag_prompt import rag_prompt
from tender_iq.config.llm_config import get_llm
from tender_iq.rag.query_transformers import build_multi_query_retrieval_chain

logger = logging.getLogger(__name__)

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
        if isinstance(obj, dict):
            value = obj.get(attr, default)
        else:
            value = getattr(obj, attr, default)
        return default if value is None else value

    dates = safe_value(tender_obj, "dates", None)
    financials = safe_value(tender_obj, "financials", None)
    fleet = safe_value(tender_obj, "fleet", None)

    lines = [
        f"- Bid ID: {safe_value(tender_obj, 'bid_id')}",
        f"- Contract Period / Duration: {safe_value(dates, 'contract_period')} "
        f"({safe_value(dates, 'duration_months')} Months)",
        f"- Bid End / Submission Date: {safe_value(dates, 'submission_deadline')}",
        f"- Opening Date: {safe_value(dates, 'opening_date')}",
        f"- Estimated Bid Value: {safe_value(financials, 'estimated_bid_value')}",
        f"- EMD Amount: {safe_value(financials, 'emd_amount')}",
        f"- Vehicle Type: {safe_value(fleet, 'vehicle_type')}",
        f"- Quantity: {safe_value(fleet, 'minimum_quantity')}",
        f"- Estimated Monthly KM: {safe_value(fleet, 'estimated_km_per_month')} KM",
    ]
    return "\n".join(lines)




def build_rag_chain(
    tender_id: str,
    chunk: list,
    tender_obj=None,
    stage_latencies_ms: dict[str, float] | None = None,
    capture_evidence: bool = False,
):
    timings = stage_latencies_ms if stage_latencies_ms is not None else {}
    
    retriever = get_ensemble_retriever(
        tender_id=tender_id,
        chunks=chunk,
        stage_latencies_ms=timings,
    )
    llm = get_llm()
    parser = StrOutputParser()

    retrieval_chain = build_multi_query_retrieval_chain(retriever, llm, timings)


    # 1. Format metadata and partially bind to prompt upfront
    metadata_str = format_tender_metadata(tender_obj)
    configured_prompt = rag_prompt.partial(metadata_specs=metadata_str)
    
    def answer_with_sources(question: str):
        latency_breakdown_ms = dict(timings)
        retrieved_docs = retrieval_chain.invoke(question) #obtains document
        latency_breakdown_ms.update(timings)
        prompt_value = configured_prompt.invoke({  #combines that text, structured metadata and the question.
            "context": format_docs(retrieved_docs), #formats their text
            "question": question,
        })

        if capture_evidence:
            # Snapshot the actual model input before generation, without truncating evidence.
            evidence_chunks = []
            for position, doc in enumerate(retrieved_docs, start=1):
                metadata = doc.model_dump(mode="json")["metadata"]
                stored_id = doc.id or metadata.get("chunk_id")
                identity = json.dumps(
                    {"tender_id": tender_id, "text": doc.page_content, "metadata": metadata},
                    sort_keys=True,
                    ensure_ascii=False,
                )
                evidence_chunks.append({
                    "chunk_id": str(stored_id) if stored_id is not None else hashlib.sha256(identity.encode("utf-8")).hexdigest(),
                    "id_source": "stored" if stored_id is not None else "derived_sha256",
                    "position": position,
                    "text": doc.page_content,
                    "metadata": metadata,
                })
            evaluation_evidence = {
                "retrieved_chunks": evidence_chunks,
                "retrieval_order": "Multi-query results combined in query order and deduplicated; no global reranking.",
                "structured_overview": metadata_str,
                "prompt_messages": [
                    {
                        "role": {"human": "user", "ai": "assistant"}.get(message.type, message.type),
                        "content": message.model_dump(mode="json")["content"],
                    }
                    for message in prompt_value.to_messages()
                ],
            }

        # 1. Capture the raw AIMessage from the model
        answer_started_at = time.perf_counter()
        try:
            raw_response = llm.invoke(prompt_value) #sends the completed prompt to the model.
        finally:
            duration_ms = round((time.perf_counter() - answer_started_at) * 1000, 2)
            latency_breakdown_ms["answer_generation_ms"] = duration_ms
            timings["answer_generation_ms"] = duration_ms
            logger.info("Stage [Answer Call] completed in %.2f ms", duration_ms)
        
        # 2. Parse text content
        answer = parser.invoke(raw_response)
        
        # 3. Extract token usage metadata from Gemini/LangChain
        tokens = 0
        if hasattr(raw_response, "usage_metadata") and raw_response.usage_metadata:
            tokens = raw_response.usage_metadata.get("total_tokens", 0)

        result = {
            "answer": answer, 
            "sources": retrieved_docs,
            "tokens_used": tokens,
            "latency_breakdown_ms": latency_breakdown_ms,
        }
        if capture_evidence:
            result["evaluation_evidence"] = evaluation_evidence
        return result

    return RunnableLambda(answer_with_sources)
