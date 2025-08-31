from flask import session, current_app
from .stt_deepgram import transcribe_audio as transcribe_deepgram
from .stt_mistral import transcribe_audio as transcribe_mistral

def transcribe_audio(file_path, config):
    """
    Dispatches the transcription task to the appropriate STT service
    based on the user's session settings. Defaults to Mistral.
    """
    provider = session.get('stt_provider', 'mistral')

    if provider == 'deepgram':
        return transcribe_deepgram(file_path, config)
    
    # Default to Mistral
    return transcribe_mistral(file_path, config)
