import json
from langchain.globals import set_verbose
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from pydantic import BaseModel, Field

# Suppress the verbose warning by setting the global verbosity flag
set_verbose(False)

def format_duration(seconds):
    """Formats duration in seconds to a 'X min Y sec' string."""
    if seconds is None:
        return "N/A"
    minutes = int(seconds // 60)
    remaining_seconds = int(seconds % 60)
    if minutes > 0:
        return f"{minutes} min {remaining_seconds} sec"
    return f"{remaining_seconds} sec"

# Define the desired JSON structure for the score
class QuizGrade(BaseModel):
    score: int = Field(description="The score from 1 to 5, where 1 is poor and 5 is excellent.")

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
        max_retries=max_retries
    )

def evaluate_answer(question, answer, category, config, duration=None):
    """
    Evaluates a user's answer using a two-step LLM process via OpenRouter.
    1. A reasoning model generates a detailed justification.
    2. A structured output model provides a score based on the justification.
    """
    try:
        api_key = config.get('OPENROUTER_API_KEY')
        if not api_key:
            return {"score": 0, "justification": "Error: OPENROUTER_API_KEY not configured."}

        # --- Step 1: Get detailed justification from the reasoning model ---
        reasoning_client = get_openrouter_client(
            config['REASONING_MODEL'],
            config['REASONING_TEMPERATURE'],
            config['REASONING_TOP_K'],
            api_key,
            config.get('OPENROUTER_MAX_RETRIES', 3)
        )
        
        reasoning_context_system = config.get("REASONING_CONTEXT_SYSTEM", "")
        reasoning_context_user = config.get("REASONING_CONTEXT_USER", "")

        formatted_duration = format_duration(duration)

        reasoning_prompt_text = f"""{reasoning_context_system}
            You are an expert evaluator in the field of {{category}}. Your task is to provide a detailed, constructive critique of a user's answer to a quiz question.
            
            Category: {{category}}
            Question: "{{question}}"
            User's Answer: "{{answer}}"
            Answer Duration: {formatted_duration}
            
            {reasoning_context_user}
            
            Please provide a clear rationale for why the answer is correct, partially correct, or incorrect. Be encouraging but accurate.
            Do not assign a score, only provide the written justification."""
        
        reasoning_prompt = ChatPromptTemplate.from_template(reasoning_prompt_text)
        
        reasoning_chain = reasoning_prompt | reasoning_client | StrOutputParser()
        justification = reasoning_chain.invoke({
            "question": question,
            "answer": answer,
            "category": category
        })

        # --- Step 2: Get a structured score based on the justification ---
        structured_client = get_openrouter_client(
            config['STRUCTURED_OUTPUT_MODEL'],
            config['STRUCTURED_OUTPUT_TEMPERATURE'],
            config['STRUCTURED_OUTPUT_TOP_K'],
            api_key,
            config.get('OPENROUTER_MAX_RETRIES', 3)
        ).with_structured_output(QuizGrade)

        structured_context_system = config.get("STRUCTURED_CONTEXT_SYSTEM", "")
        structured_context_user = config.get("STRUCTURED_CONTEXT_USER", "")

        scoring_prompt_text = f"""{structured_context_system}
            You are a strict but fair judge. Based on the following quiz question, the user's answer, and a detailed evaluation, please assign a score from 1 to 5.
            
            Category: {{category}}
            Question: "{{question}}"
            User's Answer: "{{answer}}"
            Answer Duration: {formatted_duration}
            Evaluation: "{{justification}}"
            
            {structured_context_user}
            
            Provide only the score from 1 to 5 in the required JSON format."""
            
        scoring_prompt = ChatPromptTemplate.from_template(scoring_prompt_text)
        
        scoring_chain = scoring_prompt | structured_client
        grade = scoring_chain.invoke({
            "justification": justification,
            "question": question,
            "answer": answer,
            "category": category
        })

        return {
            "score": grade.score,
            "justification": justification
        }

    except Exception as e:
        print(f"Error during evaluation: {e}")
        return {
            "score": 0,
            "justification": f"An error occurred during evaluation: {e}"
        }
