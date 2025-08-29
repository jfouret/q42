import time
from deepgram import DeepgramClient, PrerecordedOptions, FileSource

def transcribe_audio(file_path, config):
    """
    Transcribes an audio file using the Deepgram API, with a retry mechanism.

    Args:
        file_path (str): The absolute path to the audio file.
        config (dict): A dictionary containing the Deepgram configuration.

    Returns:
        A string containing the transcribed text, or an error message.
    """
    api_key = config.get('DEEPGRAM_API_KEY')
    model = config.get('DEEPGRAM_MODEL')
    language = config.get('DEEPGRAM_LANGUAGE')
    max_retries = config.get('DEEPGRAM_MAX_RETRIES', 3)
    retry_delay = config.get('DEEPGRAM_RETRY_DELAY', 1) # in seconds

    if not api_key:
        return "Error: DEEPGRAM_API_KEY not configured."

    deepgram = DeepgramClient(api_key)

    with open(file_path, "rb") as file:
        buffer_data = file.read()

    payload: FileSource = {
        "buffer": buffer_data,
    }

    options = PrerecordedOptions(
        model=model,
        language=language,
        smart_format=True,
    )

    for attempt in range(max_retries):
        try:
            response = deepgram.listen.rest.v("1").transcribe_file(payload, options)
            transcript = response.results.channels[0].alternatives[0].transcript
            return transcript
        except Exception as e:
            print(f"Deepgram Exception (Attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                return f"Error: Could not transcribe audio after {max_retries} attempts. {e}"

    return "Error: Transcription failed after all retries."
