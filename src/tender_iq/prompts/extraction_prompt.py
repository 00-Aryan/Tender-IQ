from tender_iq.config.ask_llm import ask_llm
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv

load_dotenv()


with open("docs/output_text.txt") as file:
    document_text = file.read()


template = ChatPromptTemplate(
    [('system',"""You are a tender document analyst specializing in vehicle/transport tenders.Extract information ONLY from the provided document. If a field is not explicitly mentioned, return null.Never guess. Never infer beyond what is written"""),
     ('human','Fetch the {extraction_target} from {document_text} ')]
)

complete_prompt = template.invoke({"extraction_target": "deadline", "document_text": document_text})

response = ask_llm(prompt=complete_prompt, model_provider='openai')
print(response)
