import os
from dotenv import load_dotenv

# Load environment variables from a .env file
load_dotenv()

# Define base directory for the project
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_DIR = os.path.join(BASE_DIR, 'database')

# Ensure the database directory exists before the app uses it
if not os.path.exists(DB_DIR):
    os.makedirs(DB_DIR)

def _read_file_content(path):
    """Helper function to read file content. Returns empty string if file not found."""
    if path and os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        except IOError as e:
            print(f"Error reading file {path}: {e}")
            return ""
    return ""

class Config:
    """Base configuration."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'a_default_secret_key_for_development')
    
    # Database configuration using an absolute path
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', f'sqlite:///{os.path.join(DB_DIR, "quiz.db")}')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Deepgram API Configuration
    DEEPGRAM_API_KEY = os.environ.get('DEEPGRAM_API_KEY')
    DEEPGRAM_MODEL = os.environ.get('DEEPGRAM_MODEL', 'nova-3')
    DEEPGRAM_LANGUAGE = os.environ.get('DEEPGRAM_LANGUAGE', 'multi')

    # OpenRouter LLM Configuration
    OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
    
    # Model for generating the detailed, human-like evaluation
    REASONING_MODEL = os.environ.get("REASONING_MODEL", "google/gemini-2.5-pro")
    REASONING_TEMPERATURE = float(os.environ.get("REASONING_TEMPERATURE", 0.4))
    REASONING_TOP_K = int(os.environ.get("REASONING_TOP_K", 10))
    
    # Model for generating the structured JSON output (score)
    # This should be a model that officially supports structured outputs on OpenRouter
    STRUCTURED_OUTPUT_MODEL = os.environ.get("STRUCTURED_OUTPUT_MODEL", "mistralai/mistral-medium-3.1")
    STRUCTURED_OUTPUT_TEMPERATURE = float(os.environ.get("STRUCTURED_OUTPUT_TEMPERATURE", 0))
    STRUCTURED_OUTPUT_TOP_K = int(os.environ.get("STRUCTURED_OUTPUT_TOP_K", 1))

    # Optional context for prompts, loaded from files
    REASONING_CONTEXT_USER = _read_file_content(os.environ.get("REASONING_CONTEXT_USER"))
    REASONING_CONTEXT_SYSTEM = _read_file_content(os.environ.get("REASONING_CONTEXT_SYSTEM"))
    STRUCTURED_CONTEXT_USER = _read_file_content(os.environ.get("STRUCTURED_CONTEXT_USER"))
    STRUCTURED_CONTEXT_SYSTEM = _read_file_content(os.environ.get("STRUCTURED_CONTEXT_SYSTEM"))

    # Directory for questions
    QUESTIONS_DIR = os.environ.get("QUESTIONS_DIR", os.path.join(BASE_DIR, 'data', 'questions'))

    # Speechify TTS Configuration
    SPEECHIFY_API_TOKEN = os.environ.get('SPEECHIFY_API_TOKEN')
    TTS_AUDIO_DIR = os.environ.get("TTS_AUDIO_DIR", os.path.join(BASE_DIR, 'quiz_app', 'static', 'audio', 'tts'))
