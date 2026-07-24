from src.tender_iq.config.llm_config import get_llm

llm = get_llm()




response1 = llm.invoke("What is RAG in 2 sentences?")
print("Default model:", response1.content)

# Call 2 — override model at runtime (this is what configurable_fields enables)
response2 = llm.with_config(
    configurable={
            "tenderiq_model_provider": "openai", # Switches the internal provider class
            "tenderiq_base_url": "https://openrouter.ai/api/v1",
            "tenderiq_model": "openai/gpt-4o-mini", # Adjust to your OpenRouter model name
            "tenderiq_temperature": 0.7,
        }
).invoke("What is RAG in 2 sentences?")
print("Overridden model:", response2.content)

