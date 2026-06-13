"""
TTS engine based on Kokoro-ONNX.

Each character gets a consistent voice profile based on their gender:
  - Masculine pool: American male voices (am_adam, am_michael)
  - Feminine pool:  American female voices (af_bella, af_jessica)

Pitch shift technique:
  The WAV is written with claimed_rate = real_rate * 2^(semitones/12).
  The browser plays at this rate → pitch shifted without extra libraries.
  Synthesis speed is compensated so playback duration stays the same.

Required models in models/ folder:
  models/kokoro-v1.0.onnx
  models/voices-v1.0.bin
(download with: python download_models.py)
"""
from __future__ import annotations

import io
import os
import threading

import numpy as np
from game import config as cfg

_kokoro = None
_lock = threading.Lock()

MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models")
MODEL_PATH  = os.path.join(MODELS_DIR, "kokoro-v1.0.onnx")
VOICES_PATH = os.path.join(MODELS_DIR, "voices-v1.0.bin")

# Narrator: deep British male, slightly lowered
_NARRATOR_VOICE = "bm_george"
_NARRATOR_PITCH = -2

# Profiles: (base_voice, secondary_voice, base_ratio, pitch_semitones, speed_base)
# base_ratio  : weight of base voice (1.0 = pure base)
# pitch       : semitones via WAV sample rate (negative = deeper, positive = higher)
# speed       : Kokoro base synthesis speed

_MASCULINE_PROFILES = [
    ("am_adam",    None,         1.00,  0,  1.00),   # 0  neutral male
    ("am_adam",    "am_michael", 0.70, -3,  0.93),   # 1  deep
    ("am_michael", None,         1.00, -5,  0.89),   # 2  very deep
    ("am_adam",    "am_michael", 0.85, -1,  0.96),   # 3  slightly deep, calm
    ("am_michael", "am_adam",    0.65, -4,  0.91),   # 4  deep raspy
    ("am_adam",    None,         1.00, -2,  0.97),   # 5  neutral deep
]

_FEMININE_PROFILES = [
    ("af_bella",   None,         1.00, +4,  1.06),   # 0  clear female
    ("af_jessica", "af_bella",   0.78, +2,  1.04),   # 1  medium female
    ("af_bella",   None,         1.00, +5,  1.13),   # 2  high, light
    ("af_bella",   "af_jessica", 0.80, +3,  1.07),   # 3  lively female
    ("af_jessica", "af_bella",   0.82, -1,  0.97),   # 4  deep mysterious
    ("af_jessica", None,         1.00, +6,  1.18),   # 5  very high, young
]

_voice_arrays: dict[str, np.ndarray] = {}


def _load():
    global _kokoro
    from kokoro_onnx import Kokoro
    _kokoro = Kokoro(MODEL_PATH, VOICES_PATH)
    all_voices = _kokoro.get_voices()

    narrator = _kokoro.get_voice_style(_NARRATOR_VOICE)
    _voice_arrays["narrator"] = narrator.copy()

    for prefix, profiles in (("m", _MASCULINE_PROFILES), ("f", _FEMININE_PROFILES)):
        for i, (base_voice, secondary, base_ratio, _pitch, _speed) in enumerate(profiles):
            base = _kokoro.get_voice_style(base_voice)
            if secondary and secondary in all_voices and base_ratio < 1.0:
                sec = _kokoro.get_voice_style(secondary)
                blended = base * base_ratio + sec * (1.0 - base_ratio)
            else:
                blended = base.copy()
            _voice_arrays[f"{prefix}_{i}"] = blended


def ensure_loaded():
    global _kokoro
    if _kokoro is None:
        with _lock:
            if _kokoro is None:
                _load()


def is_ready() -> bool:
    return os.path.exists(MODEL_PATH) and os.path.exists(VOICES_PATH)


def synthesize(
    text: str,
    character_index: int | None = None,
    is_narrator: bool = False,
    speed_multiplier: float = 1.0,
    gender: str = "m",
) -> bytes:
    """
    Generate a WAV for the given text.

    character_index  : index in the gendered pool (auto cycles)
    is_narrator      : True for the narrator voice
    speed_multiplier : global speed factor (user slider)
    gender           : "m" (masculine) or "f" (feminine)
    """
    import soundfile as sf

    ensure_loaded()
    speed_multiplier = max(0.5, min(2.5, float(speed_multiplier)))

    if is_narrator or character_index is None:
        voice = _voice_arrays["narrator"]
        base_speed = float(cfg.get("TTS_NARRATOR_SPEED"))
        pitch = _NARRATOR_PITCH
    else:
        profiles = _FEMININE_PROFILES if gender == "f" else _MASCULINE_PROFILES
        prefix = "f" if gender == "f" else "m"
        idx = character_index % len(profiles)
        _bv, _sv, _br, pitch, base_speed = profiles[idx]
        voice = _voice_arrays.get(f"{prefix}_{idx}", _voice_arrays["narrator"])

    # Pitch factor: 2^(semitones/12)
    pf = 2.0 ** (pitch / 12.0)

    # Synthesis speed compensated to keep final playback duration unchanged
    synthesis_speed = max(0.5, min(2.0, base_speed * speed_multiplier / pf))

    with _lock:
        samples, sample_rate = _kokoro.create(
            text,
            voice=voice,
            speed=synthesis_speed,
            lang="en-us",
        )

    # Pitch shift: browser reads at claimed_rate Hz instead of sample_rate Hz
    claimed_rate = int(round(sample_rate * pf))

    buf = io.BytesIO()
    sf.write(buf, samples, claimed_rate, format="WAV")
    buf.seek(0)
    return buf.read()
