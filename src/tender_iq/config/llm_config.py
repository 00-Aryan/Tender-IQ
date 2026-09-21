from dotenv import load_dotenv
from langchain.chat_models import init_chat_model

load_dotenv()

PROVIDER_CONFIGS = {
    "gemini": { 
            "tenderiq_model":"gemini-3.1-flash-lite",       
            "tenderiq_model_provider":"google_genai", 
            "tenderiq_temperature":0.3,},
    "openai": {
            "tenderiq_model_provider": "openai", # Switches the internal provider class
            "tenderiq_base_url": "https://openrouter.ai/api/v1",
            "tenderiq_model": "openai/gpt-4o-mini", # Adjust to your OpenRouter model name
            "tenderiq_temperature": 0.7,},
}


def get_llm():

    model = init_chat_model(
        model="gemini-3.1-flash-lite",       
        model_provider="google_genai", 
        configurable_fields="any",  
        config_prefix="tenderiq",
        temperature=0,
    )

    return model




