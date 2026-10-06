"""Gemini integration (REST, no SDK needed). Everything degrades gracefully when no key is set."""
from __future__ import annotations

import requests

from .. import config

_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def available() -> bool:
    return bool(config.GEMINI_API_KEY)


def _call(prompt: str, temperature: float = 0.2, max_tokens: int = 400) -> str | None:
    if not available():
        return None
    try:
        r = requests.post(
            _URL.format(model=config.GEMINI_MODEL),
            params={"key": config.GEMINI_API_KEY},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
            },
            timeout=30,
        )
        r.raise_for_status()
        parts = r.json()["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts).strip() or None
    except Exception as e:
        print(f"[llm] Gemini call failed: {type(e).__name__}: {e}")
        return None


def answer(question: str, context: str, facts_text: str, history: list[dict]) -> str | None:
    hist = "\n".join(f"{m['role'].title()}: {m['content']}" for m in history[-6:]) or "(none)"
    prompt = f"""You are "Smart Circular AI", a helpful college assistant. Answer the student's question
using ONLY the circular excerpts below. Be concise (1-3 sentences), direct and friendly.
If the answer is not in the circular, say you could not find it in the circular. Never invent dates, times or places.
Resolve follow-up questions ("Where?", "And the deadline?") using the conversation history.

KEY FACTS EXTRACTED BY NLP:
{facts_text}

CIRCULAR EXCERPTS:
{context}

CONVERSATION SO FAR:
{hist}

STUDENT QUESTION: {question}
ANSWER:"""
    return _call(prompt)


def summarize(text: str) -> str | None:
    prompt = f"Summarize this college circular in 2-3 plain sentences for students. Include date, time, venue, who it is for and any deadline if present.\n\n{text[:6000]}"
    return _call(prompt, max_tokens=250)
