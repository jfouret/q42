from flask import session, current_app
from .stt_deepgram import transcribe_audio as transcribe_deepgram
from .stt_mistral import transcribe_audio as transcribe_mistral

def transcribe_audio(file_path, config, provider='mistral'):
    """
    Dispatches the transcription task to the appropriate STT service.
    Defaults to Mistral.
    """
    if provider == 'deepgram':
        return transcribe_deepgram(file_path, config)
    
    # Default to Mistral
    return transcribe_mistral(file_path, config)
