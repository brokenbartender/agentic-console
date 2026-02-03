from __future__ import annotations

import time
from typing import Optional

try:
    import sounddevice as sd
    import numpy as np
except Exception:
    sd = None
    np = None

try:
    import whisper
except Exception:
    whisper = None

try:
    import pyttsx3
except Exception:
    pyttsx3 = None


def record_and_transcribe(seconds: int = 5, model_name: str = "base") -> str:
    if sd is None or np is None:
        raise RuntimeError("sounddevice/numpy not installed")
    if whisper is None:
        raise RuntimeError("whisper not installed")
    seconds = max(1, min(seconds, 60))
    sample_rate = 16000
    audio = sd.rec(int(seconds * sample_rate), samplerate=sample_rate, channels=1, dtype="float32")
    sd.wait()
    audio = audio.flatten()
    model = whisper.load_model(model_name)
    result = model.transcribe(audio, fp16=False)
    return (result.get("text") or "").strip()


def speak_text(text: str, rate: Optional[int] = None) -> None:
    if pyttsx3 is None:
        raise RuntimeError("pyttsx3 not installed")
    engine = pyttsx3.init()
    if rate:
        engine.setProperty("rate", rate)
    engine.say(text)
    engine.runAndWait()


def wait(seconds: float) -> None:
    time.sleep(seconds)
