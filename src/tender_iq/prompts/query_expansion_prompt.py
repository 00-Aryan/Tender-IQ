from langchain_core.prompts import ChatPromptTemplate

query_expansion_prompt = ChatPromptTemplate.from_template(
    """You are a tender retrieval specialist for GeM (Government e-Marketplace) documents.
Given the following user question, generate 3 alternative query variations to search the document database.
Output the queries separated by newlines, with no numbering, bullet points, preamble, or markdown formatting.

Query 1: Canonical GeM tabular term (e.g., "Bid End Date/Time", "EMD Detail", "ePBG Percentage").
Query 2: Standard commercial/procurement phrasing (e.g., "bid submission last date", "earnest money deposit").
Query 3: A conversational synonym variation of the user's intent.

User question: {question}"""
)
