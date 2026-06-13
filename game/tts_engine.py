"""
Moteur TTS basé sur Kokoro-ONNX.

Chaque personnage reçoit un profil cohérent avec son genre (prénom) :
  - pool masculin : pitches négatifs/neutres + voix masculines anglaises
  - pool féminin  : pitches positifs/neutres + voix féminines anglaises

Technique pitch shift :
  Le WAV est écrit avec claimed_rate = real_rate * 2^(semitones/12).
  Le navigateur joue à ce taux → pitch décalé sans librairie supplémentaire.
  La vitesse de synthèse est compensée pour que la durée reste identique.

Modèles requis dans le dossier models/ :
  models/kokoro-v1.0.onnx
  models/voices-v1.0.bin
(télécharger avec : python download_models.py)
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

# Narrateur : voix française pure, plus grave
_NARRATOR_PITCH = -3

# Profils : (fr_ratio, voix_secondaire, pitch_semitones, speed_base)
# fr_ratio   : poids de ff_siwis (1.0 = pur français)
# secondaire : voix anglaise mélangée pour varier le timbre
# pitch      : demi-tons via sample_rate WAV (négatif = grave, positif = aigu)
# speed      : vitesse de base Kokoro

_MASCULINE_PROFILES = [
    (1.00, None,          0,  1.00),   # 0  neutre masculin
    (0.68, "am_adam",    -3,  0.93),   # 1  grave marqué
    (0.60, "am_michael", -5,  0.89),   # 2  très grave (vieux sage)
    (0.85, "am_adam",    -1,  0.96),   # 3  légèrement grave, posé
    (0.65, "am_adam",    -4,  0.91),   # 4  grave rauque
    (1.00, None,         -2,  0.97),   # 5  neutre légèrement grave
]

_FEMININE_PROFILES = [
    (0.72, "af_bella",   +4,  1.06),   # 0  féminin clair
    (0.78, "af_jessica", +2,  1.04),   # 1  féminin médium
    (1.00, None,         +5,  1.13),   # 2  voix haute, légère
    (0.80, "af_bella",   +3,  1.07),   # 3  féminin vif
    (0.82, "af_bella",   -1,  0.97),   # 4  féminin grave, mystérieux
    (0.75, "af_jessica", +6,  1.18),   # 5  très aigu, jeune
]

_voice_arrays: dict[str, np.ndarray] = {}


def _load():
    global _kokoro
    from kokoro_onnx import Kokoro
    _kokoro = Kokoro(MODEL_PATH, VOICES_PATH)

    fr = _kokoro.get_voice_style("ff_siwis")
    all_voices = _kokoro.get_voices()

    _voice_arrays["narrator"] = fr.copy()

    for prefix, profiles in (("m", _MASCULINE_PROFILES), ("f", _FEMININE_PROFILES)):
        for i, (fr_ratio, secondary, _pitch, _speed) in enumerate(profiles):
            if secondary and secondary in all_voices and fr_ratio < 1.0:
                sec = _kokoro.get_voice_style(secondary)
                blended = fr * fr_ratio + sec * (1.0 - fr_ratio)
            else:
                blended = fr.copy()
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
    Génère un WAV pour le texte donné.

    character_index  : index dans le pool genré (cycle automatique)
    is_narrator      : True pour la voix du narrateur
    speed_multiplier : facteur global de vitesse (slider utilisateur)
    gender           : "m" (masculin) ou "f" (féminin)
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
        _fr_ratio, _secondary, pitch, base_speed = profiles[idx]
        voice = _voice_arrays.get(f"{prefix}_{idx}", _voice_arrays["narrator"])

    # Facteur de pitch : 2^(semitones/12)
    pf = 2.0 ** (pitch / 12.0)

    # Vitesse de synthèse compensée pour conserver la durée finale
    synthesis_speed = max(0.5, min(2.0, base_speed * speed_multiplier / pf))

    with _lock:
        samples, sample_rate = _kokoro.create(
            text,
            voice=voice,
            speed=synthesis_speed,
            lang="fr-fr",
        )

    # Pitch shift : navigateur lit à claimed_rate Hz au lieu de sample_rate Hz
    claimed_rate = int(round(sample_rate * pf))

    buf = io.BytesIO()
    sf.write(buf, samples, claimed_rate, format="WAV")
    buf.seek(0)
    return buf.read()
