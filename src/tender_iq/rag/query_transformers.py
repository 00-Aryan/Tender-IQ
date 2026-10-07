import logging
import time

from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_core.output_parsers import StrOutputParser
from tender_iq.prompts.query_expansion_prompt import query_expansion_prompt

logger = logging.getLogger(__name__)

def parse_queries(inputs: dict) -> list[str]:
    original_question = inputs["question"]
    llm_output = inputs["llm_output"]
    queries = [original_question]
    for q in llm_output.split("\n"):
        q_stripped = q.strip()
        if q_stripped:
            queries.append(q_stripped)
    return queries

def build_multi_query_retrieval_chain(retriever, llm, stage_latencies_ms=None):
    parser = StrOutputParser()
    timings = stage_latencies_ms if stage_latencies_ms is not None else {}
    expansion_chain = query_expansion_prompt | llm | parser

    def expand_query(inputs: dict):
        started_at = time.perf_counter()
        try:
            return expansion_chain.invoke(inputs)
        finally:
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            timings["query_expansion_ms"] = duration_ms
            logger.info("Stage [Expansion Call] completed in %.2f ms", duration_ms)

    def retrieve_and_deduplicate(queries: list[str]):
        all_docs = []
        seen_content_hashes = set()
        
        # Use batch execution for parallel retrieval
        started_at = time.perf_counter()
        try:
            batch_results = retriever.batch(queries)
        finally:
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            timings["retrieval_ms"] = duration_ms
            logger.info("Stage [Retrieval] completed in %.2f ms", duration_ms)
        
        for docs in batch_results:
            for doc in docs:
                # Deduplicate based on a hash of the stripped content
                content_hash = hash(doc.page_content.strip())
                if content_hash not in seen_content_hashes:
                    seen_content_hashes.add(content_hash)
                    all_docs.append(doc)
                    
        return all_docs

    retrieval_chain = (
        {"question": RunnablePassthrough()}
        | RunnablePassthrough.assign(
            llm_output=(
                RunnableLambda(expand_query)
            )
        )
        | RunnableLambda(parse_queries)
        | RunnableLambda(retrieve_and_deduplicate)
    )
    
    return retrieval_chain
