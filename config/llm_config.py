from dotenv import load_dotenv
from langchain.chat_models import init_chat_model

load_dotenv()


def get_llm():

    # Use gemini-2.5-flash instead of the decommissioned 1.5 version
    model = init_chat_model(
        model="gemini-3.1-flash-lite",       
        model_provider="google_genai", 
        configurable_fields="any",  
        config_prefix="tenderiq",
        temperature=0,
    )

    return model




