"""gTTS voice responses with an on-disk cache."""
from __future__ import annotations

import hashlib
import re

from ..config import AUDIO_DIR

SUPPORTED = {"en", "hi", "ta", "te", "ml", "kn", "bn", "mr", "gu", "ur"}


def _plain(text: str) -> str:
    text = re.sub(r"[*_`#>]+", "", text)
    text = re.sub(r"\s*\n+\s*", ". ", text)
    return text.strip()


def speak(text: str, lang: str = "en"):
    """Return the Path of an MP3 for ``text`` (generating it with gTTS if needed)."""
    from gtts import gTTS

    lang = lang if lang in SUPPORTED else "en"
    clean = _plain(text)[:1500]
    key = hashlib.sha1(f"{lang}:{clean}".encode()).hexdigest()
    path = AUDIO_DIR / f"{key}.mp3"
    if not path.exists():
        gTTS(clean, lang=lang, tld="co.in" if lang == "en" else "com").save(str(path))
    return path
