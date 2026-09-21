from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel , Field 
from typing import Optional
from tender_iq.config.llm_config import get_llm


class TenderSummary(BaseModel): 
    emd_amount: Optional[float] = Field( description="earnest money deposit ")
    deadline: Optional[str] = Field(description="deadline of the tender ")
    vehicle_type: Optional[str] = Field(description="Vehicle category only (e.g., SUV, Bus, Truck). Do not include make, model, or year.")


with open("docs/output_text.txt") as file:
    document_text = file.read()

parser = PydanticOutputParser(pydantic_object=TenderSummary)

prompt = ChatPromptTemplate.from_messages([
    ("system", "Extract tender information.\n{format_instructions}"),
    ("human", "{document_text}")
]).partial(format_instructions=parser.get_format_instructions())

chain = prompt | get_llm() | parser

result = chain.invoke({"document_text": document_text})

print(result)
# print(result.emd_amount)