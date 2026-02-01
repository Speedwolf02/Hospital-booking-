import pyttsx3
import uuid
import os

# ================= CONFIG ================= #

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TTS_DIR = os.path.join(BASE_DIR, "static", "tts")

os.makedirs(TTS_DIR, exist_ok=True)

# ================= INIT ENGINE ================= #

engine = pyttsx3.init()

# Optional: select a clear English voice
voices = engine.getProperty("voices")
for v in voices:
    if "english" in v.name.lower():
        engine.setProperty("voice", v.id)
        break

engine.setProperty("rate", 165)   # Speech speed
engine.setProperty("volume", 1.0) # Max volume

# ================= FUNCTION ================= #

def synthesize_to_wav(text):
    """
    Convert text → speech WAV file
    Returns filename only
    """

    filename = f"tts_{uuid.uuid4().hex}.wav"
    output_path = os.path.join(TTS_DIR, filename)

    engine.save_to_file(text, output_path)
    engine.runAndWait()

    return filename
