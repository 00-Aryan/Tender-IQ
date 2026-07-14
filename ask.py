from config.llm_config import get_llm


def extract_content(response) -> str:
    content = response.content
    if isinstance(content, list):
        return content[0]['text']
    return content

def ask_llm(question: str, model_provider: str) -> str:
    llm = get_llm()
    if model_provider == "gemini":
        response = llm.invoke(question)
        output = extract_content(response)
        
        print(f"\n Gemini Output \n{output}")
        return output
    

    elif model_provider == "openai":
        configured_llm = llm.with_config(
            configurable={
            "tendderiq_model_provider": "openai", # Switches the internal provider class
            "tendderiq_base_url": "https://openrouter.ai/api/v1",
            "tendderiq_model": "openai/gpt-4o-mini", # Adjust to your OpenRouter model name
            "tendderiq_temperature": 0.7,
        }
        )
        response = configured_llm.invoke(question)
        output = extract_content(response)
        

        print(f"\n OpenAI Output \n{output}")
        return output
    else:
        raise ValueError(f"Unsupported provider: {model_provider}")
    
if __name__ == "__main__":
    test_question = "What is the capital of India?"
    ask_llm(test_question, model_provider="gemini")
    ask_llm(test_question, model_provider="openai")