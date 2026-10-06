"""Extractive, fact-grounded answer generation (used directly, and as grounding/fallback for Gemini)."""
from __future__ import annotations

import re
from typing import Callable

from .nlp import split_sentences

RankFn = Callable[[str, list[str]], list[float]]


def _cap(s: str) -> str:
    return s[:1].upper() + s[1:]


def _top(question: str, sents: list[str], rank: RankFn, n: int = 3) -> list[str]:
    if len(sents) <= n:
        return sents
    sc = rank(question, sents)
    keep = sorted(sorted(range(len(sents)), key=lambda i: -sc[i])[:n])
    return [sents[i] for i in keep]


def _humanize_eligibility(s: str) -> str:
    m = re.match(r"(?i)^\s*(eligible students|eligibility|eligible|open to|who can attend)\s*[:\-]\s*(.+?)\.?$", s)
    if not m:
        return s
    val = m.group(2).strip()
    if "student" in val.lower():
        return f"{_cap(val)} are eligible to attend."
    return f"Eligibility: {val}."


def compose(intent: str, question: str, facts: dict, rank: RankFn) -> tuple[str, list[str]] | None:
    """Return (answer, evidence_sentences) or None when the circular has nothing for this intent."""
    phrase = _cap(facts.get("phrase") or "The event")
    cats = facts.get("cats", {})
    ev, venue, dl = facts.get("event_date"), facts.get("venue"), facts.get("deadline")
    t_start, t_end = facts.get("time_start"), facts.get("time_end")
    time = t_start or facts.get("time")

    if intent == "event_date" and ev:
        rng = re.search(r"\bto\b|-|–", ev["text"])
        a = f"{phrase} is " + (f"scheduled from {ev['text']}" if rng else f"on {ev['text']}")
        if time:
            a += f" at {time}"
        if venue:
            a += f" in {venue}"
        return a + ".", [ev["sentence"]]

    if intent == "event_time" and time:
        asks_end = re.search(r"\b(end|ends|finish|over|conclude|till|until)\b", question, re.I)
        if asks_end and t_end:
            a = f"{phrase} ends at {t_end}"
        elif asks_end:
            a = f"The end time isn't mentioned; {phrase.lower()} starts at {time}"
        else:
            a = f"{phrase} starts at {time}" + (f" and ends at {t_end}" if t_end else "")
        if ev:
            a += f" on {ev['text']}"
        return a + ".", (cats.get("event_time") or [])[:2]

    if intent == "location" and venue:
        a = f"{phrase} will be held at {venue}"
        if ev:
            a += f" on {ev['text']}"
        return a + ".", (cats.get("location") or [])[:2]

    if intent == "deadline" and dl:
        label = f"{dl['label']} " if dl["label"] else ""
        return f"The {label}deadline is {dl['text']}.", [dl["sentence"]]

    if intent == "eligibility" and cats.get("eligibility"):
        strong = [s for s in cats["eligibility"] if re.search(r"(?i)\b(eligible|eligibility|open to|who can|intended for|meant for|only for)\b", s)]
        sents = _top(question, strong or cats["eligibility"], rank, 2)
        return " ".join(_humanize_eligibility(s) for s in sents), sents

    if intent in {"registration", "instructions", "fee", "contact"} and cats.get(intent):
        sents = _top(question, cats[intent], rank, 3)
        ans = " ".join(s if s.endswith((".", "!", "?")) else s + "." for s in sents)
        if intent == "contact":
            extra = [x for x in facts.get("emails", []) + facts.get("phones", []) if x not in ans]
            if extra:
                ans += " Contact: " + ", ".join(extra) + "."
        return ans, sents

    if intent == "summary":
        return facts.get("summary") or "", []

    return None


def best_sentences(question: str, text: str, rank: RankFn, n: int = 2, min_score: float = 0.12):
    sents = split_sentences(text)
    if not sents:
        return None
    sc = rank(question, sents)
    order = sorted(range(len(sents)), key=lambda i: -sc[i])[:n]
    order = [i for i in order if sc[i] >= min_score]
    if not order:
        return None
    picked = [sents[i] for i in sorted(order)]
    return " ".join(picked), picked, max(sc[i] for i in order)
