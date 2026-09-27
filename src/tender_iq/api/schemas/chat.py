"""
Pydantic schemas for Chat requests and responses.
"""
from pydantic import BaseModel, Field, field_validator

class ChatRequest(BaseModel):
    tender_id: str = Field(
        ..., 
        description="The unique identifier of the tender (GeM Bid ID or Job ID)."
    )
    query: str = Field(
        ..., 
        min_length=2,
        max_length=1000,
        description="The question or prompt to run against the tender document.",
        json_schema_extra={"example": "What is the EMD amount and submission deadline?"}
    )

    @field_validator("tender_id", "query")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        """Strips accidental leading/trailing whitespace from text inputs."""
        if isinstance(v, str):
            return v.strip()
        return v

class CitationSource(BaseModel):
    page_number: int | None = Field(
        default=None, 
        description="The source page number where the information was found."
    )
    section: str | None = Field(
        default=None, 
        description="The header or section title in the tender document."
    )
    snippet: str = Field(
        ..., 
        description="The relevant excerpt from the document used to form the answer."
    )

class ChatResponse(BaseModel):
    tender_id: str = Field(..., description="The unique identifier of the tender.")
    answer: str = Field(..., description="The generated response from the RAG pipeline.")
    citations: list[CitationSource] = Field(
        default_factory=list,
        description="List of cited document chunks supporting the answer."
    )