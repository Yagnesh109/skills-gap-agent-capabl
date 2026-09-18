import tempfile
from pathlib import Path
import speech_recognition as sr


def extract_text_from_audio_bytes(file_bytes: bytes, filename: str) -> str:
    """Transcribe spoken resume text from audio bytes (.wav, .mp3, .m4a, .flac, etc.)."""
    if not file_bytes:
        raise ValueError("Audio file is empty.")

    suffix = Path(filename).suffix.lower() or ".wav"
    recognizer = sr.Recognizer()

    # Save incoming audio bytes to temporary file
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp_file:
        temp_file.write(file_bytes)
        temp_path = Path(temp_file.name)

    converted_wav = None
    try:
        wav_path = temp_path

        if suffix not in (".wav", ".aiff", ".flac"):
            try:
                from pydub import AudioSegment
                audio_segment = AudioSegment.from_file(str(temp_path))
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as wav_file:
                    converted_wav = Path(wav_file.name)
                audio_segment.export(str(converted_wav), format="wav")
                wav_path = converted_wav
            except Exception:
                # If conversion fails or ffmpeg unavailable, attempt to open directly
                pass

        with sr.AudioFile(str(wav_path)) as source:
            audio_data = recognizer.record(source)
            text = recognizer.recognize_google(audio_data)

        if not text or not text.strip():
            raise ValueError("No spoken words could be recognized from the audio file.")

        return text.strip()
    except sr.UnknownValueError:
        raise ValueError("Could not understand the audio content. Please speak clearly into the microphone.") from None
    except sr.RequestError as exc:
        raise ValueError(f"Speech recognition service request failed: {exc}") from exc
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"Unable to process audio file: {exc}") from exc
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink(missing_ok=True)
        if converted_wav and converted_wav.exists():
            converted_wav.unlink(missing_ok=True)
