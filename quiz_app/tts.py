import os
import base64
import requests
from flask import current_app

API_URL = "https://api.sws.speechify.com/v1/audio/speech"

def generate_speech_file(question_id, question_text):
    """
    Generates a speech audio file for a given question text using Speechify's REST API.
    Saves the file to the configured TTS audio directory.
    Skips generation if the file already exists.
    """
    speechify_token = current_app.config.get('SPEECHIFY_API_TOKEN')
    if not speechify_token:
        print("Speechify API token is not configured.")
        return None, 'failed'

    audio_dir = current_app.config.get('TTS_AUDIO_DIR')
    if not os.path.exists(audio_dir):
        os.makedirs(audio_dir)

    file_path = os.path.join(audio_dir, f"question_{question_id}.wav")

    if os.path.exists(file_path):
        print(f"Audio file for question {question_id} already exists. Skipping.")
        return file_path, 'skipped'

    try:
        headers = {
            "Authorization": f"Bearer {speechify_token}",
            "Content-Type": "application/json"
        }

        ssml_input = f"""
        <speak>
            <prosody rate="+25.0%">
                <speechify:style emotion="cheerful">
                    {question_text}
                </speechify:style>
            </prosody>
        </speak>
        """

        payload = {
            "input": ssml_input,
            "voice_id": "raphael",
            "model": "simba-multilingual",
            "audio_format": "wav"
        }

        response = requests.post(API_URL, json=payload, headers=headers)

        if response.status_code == 200:
            response_data = response.json()
            audio_data_b64 = response_data.get("audio_data")
            
            if audio_data_b64:
                audio_data_bytes = base64.b64decode(audio_data_b64)
                with open(file_path, 'wb') as f:
                    f.write(audio_data_bytes)
                print(f"Successfully generated audio for question {question_id}.")
                return file_path, 'created'
            else:
                print(f"Failed to get audio_data from response for question {question_id}.")
                return None, 'failed'
        else:
            print(f"Failed to generate audio for question {question_id}. Status: {response.status_code}, Response: {response.text}")
            return None, 'failed'

    except requests.exceptions.RequestException as e:
        print(f"A network error occurred while generating speech for question {question_id}: {e}")
        return None, 'failed'
    except Exception as e:
        print(f"An unexpected error occurred while generating speech for question {question_id}: {e}")
        return None, 'failed'
