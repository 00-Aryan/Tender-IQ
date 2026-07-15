from config.llm_config import get_llm, PROVIDER_CONFIGS


def extract_content(response) -> str:
    content = response.content
    if isinstance(content, list):
        return content[0]['text']
    return content


def ask_llm(question: str, model_provider: str) -> str:
    
    if model_provider not in PROVIDER_CONFIGS:
        raise ValueError(f"Unsupported provider: {model_provider}")
    
    llm = get_llm()
    config = PROVIDER_CONFIGS[model_provider]
    configured_llm = llm.with_config(configurable=config)
    response = configured_llm.invoke(question)
    return extract_content(response)
    
if __name__ == "__main__":
    test_question = "What is the capital of India?"
    
    gemini_answer = ask_llm(test_question, model_provider="gemini")
    print(f"\nGemini Output:\n{gemini_answer}")
    
    openai_answer = ask_llm(test_question, model_provider="openai")
    print(f"\nOpenAI Output:\n{openai_answer}")