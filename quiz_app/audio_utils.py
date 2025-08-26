import wave
import contextlib

def get_audio_duration(file_path):
    """
    Calculates the duration of a WAV audio file in seconds.

    Args:
        file_path (str): The path to the WAV file.

    Returns:
        The duration of the audio file in seconds (float), or 0.0 if an error occurs.
    """
    try:
        with contextlib.closing(wave.open(file_path, 'r')) as f:
            frames = f.getnframes()
            rate = f.getframerate()
            duration = frames / float(rate)
            return duration
    except Exception as e:
        print(f"Could not calculate duration for {file_path}: {e}")
        return 0.0
