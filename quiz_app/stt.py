from deepgram import DeepgramClient, PrerecordedOptions, FileSource

def transcribe_audio(file_path, config):
    """
    Transcribes an audio file using the Deepgram API.

    Args:
        file_path (str): The absolute path to the audio file.
        config (dict): A dictionary containing the Deepgram configuration.

    Returns:
        A string containing the transcribed text, or an error message.
    """
    try:
        api_key = config.get('DEEPGRAM_API_KEY')
        model = config.get('DEEPGRAM_MODEL')
        language = config.get('DEEPGRAM_LANGUAGE')

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

        response = deepgram.listen.rest.v("1").transcribe_file(payload, options)
        
        # Extract the transcript from the response
        transcript = response.results.channels[0].alternatives[0].transcript
        return transcript

    except Exception as e:
        print(f"Deepgram Exception: {e}")
        return f"Error: Could not transcribe audio. {e}"
