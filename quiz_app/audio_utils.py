from pydub import AudioSegment
from pydub.exceptions import CouldntDecodeError

def get_audio_duration(file_path):
    """
    Calculates the duration of an audio file in seconds using pydub.
    This supports multiple formats, including WAV and WebM.

    Args:
        file_path (str): The path to the audio file.

    Returns:
        The duration of the audio file in seconds (float), or 0.0 if an error occurs.
    """
    try:
        audio = AudioSegment.from_file(file_path)
        duration = len(audio) / 1000.0  # pydub measures in milliseconds
        return duration
    except CouldntDecodeError:
        print(f"Could not decode audio file: {file_path}. It may be corrupted or in an unsupported format.")
        return 0.0
    except Exception as e:
        print(f"Could not calculate duration for {file_path}: {e}")
        return 0.0
