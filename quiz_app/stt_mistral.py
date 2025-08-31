import os
from mistralai import Mistral
import time

def transcribe_audio(file_path, config):
    """
    Transcribes an audio file using the Mistral API (Voxtral).

    Args:
        file_path (str): The absolute path to the audio file.
        config (dict): A dictionary containing the Mistral configuration.

    Returns:
        A string containing the transcribed text, or an error message.
    """
    api_key = config.get('MISTRAL_API_KEY')
    model = "voxtral-mini-latest"
    max_retries = config.get('MISTRAL_MAX_RETRIES', 3)
    retry_delay = config.get('MISTRAL_RETRY_DELAY', 1)

    if not api_key:
        return "Error: MISTRAL_API_KEY not configured."

    for attempt in range(max_retries):
        try:
            client = Mistral(api_key=api_key)

            # 1. Upload the audio file
            with open(file_path, "rb") as f:
                uploaded_audio = client.files.upload(
                    file={
                        "content": f,
                        "file_name": f.name
                    },
                    purpose="audio"
                )

            # 2. Get a signed URL for the uploaded file
            signed_url = client.files.get_signed_url(file_id=uploaded_audio.id)

            # 3. Get the transcription using the signed URL
            transcription_response = client.audio.transcriptions.complete(
                model=model,
                file_url=signed_url.url,
            )

            # 4. Delete the file from Mistral's servers
            try:
                client.files.delete(file_id=uploaded_audio.id)
            except Exception as delete_e:
                print(f"Warning: Failed to delete file {uploaded_audio.id} from Mistral: {delete_e}")


            return transcription_response.text

        except Exception as e:
            print(f"Mistral Exception (Attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                return f"Error: Could not transcribe audio with Mistral after {max_retries} attempts. {e}"

    return "Error: Mistral transcription failed after all retries."
