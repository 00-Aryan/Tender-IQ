from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_core.output_parsers import StrOutputParser
from tender_iq.prompts.query_expansion_prompt import query_expansion_prompt

def parse_queries(inputs: dict) -> list[str]:
    original_question = inputs["question"]
    llm_output = inputs["llm_output"]
    queries = [original_question]
    for q in llm_output.split("\n"):
        q_stripped = q.strip()
        if q_stripped:
            queries.append(q_stripped)
    return queries

def build_multi_query_retrieval_chain(retriever, llm):
    parser = StrOutputParser()

    def retrieve_and_deduplicate(queries: list[str]):
        all_docs = []
        seen_content_hashes = set()
        
        # Use batch execution for parallel retrieval
        batch_results = retriever.batch(queries)
        
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
                query_expansion_prompt | llm | parser
            )
        )
        | RunnableLambda(parse_queries)
        | RunnableLambda(retrieve_and_deduplicate)
    )
    
    return retrieval_chain
