import os
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

def get_openrouter_client(model_name, temperature, top_k, api_key, max_retries):
    """Helper function to create a ChatOpenAI client for OpenRouter."""
    return ChatOpenAI(
        model=model_name,
        temperature=temperature,
        openai_api_key=api_key,
        openai_api_base="https://openrouter.ai/api/v1",
        default_headers={
            "HTTP-Referer": "http://localhost", 
            "X-Title": "AI Quizzer"
        },
        max_retries=max_retries,
        extra_body = {
            "reasoning": {"enable":False}
        }
    )

def translate_question(question_text, api_key, target_language="fr"):
    """
    Translates the question text to the target language using a chat LLM.
    """
    if not api_key:
        return "Error: OPENROUTER_API_KEY not configured."

    translation_client = get_openrouter_client(
        "google/gemini-2.5-pro",
        0.1,
        1,
        api_key,
        3
    )

    system_prompt = f"You are a translator. Translate the following text to {target_language}. Do not add any extra text, just the translation."
    
    translation_prompt_text = f"""{system_prompt}
        {{question_text}}
        """
    
    translation_prompt = ChatPromptTemplate.from_template(translation_prompt_text)
    
    translation_chain = translation_prompt | translation_client | StrOutputParser()
    
    translated_text = translation_chain.invoke({
        "question_text": question_text
    })
    
    return translated_text

def get_translated_question_path(question_id, text_dir):
    """
    Gets the path for the translated question text file.
    """
    os.makedirs(text_dir, exist_ok=True)
    return os.path.join(text_dir, f"question_{question_id}.alt.txt")

def save_translated_question(question_id, translated_text, text_dir):
    """
    Saves the translated question text to a file.
    """
    file_path = get_translated_question_path(question_id, text_dir)
    with open(file_path, "w") as f:
        f.write(translated_text)
    return file_path

def get_translated_question(question_id, text_dir):
    """
    Gets the translated question text from a file.
    """
    file_path = get_translated_question_path(question_id, text_dir)
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            return f.read()
    return None
