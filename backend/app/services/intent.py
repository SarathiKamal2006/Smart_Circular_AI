"""Question understanding: intent classification (rules + TF-IDF/Logistic-Regression) and follow-up detection."""
from __future__ import annotations

import re

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline

from .nlp import content_tokens

INTENT_LABELS = {
    "event_date": "Event Date",
    "event_time": "Event Time",
    "location": "Location",
    "eligibility": "Eligibility",
    "deadline": "Deadline",
    "registration": "Registration",
    "contact": "Contact",
    "instructions": "Instructions",
    "fee": "Fee / Payment",
    "summary": "General / Summary",
}

SEED = {
    "event_date": [
        "when is the seminar", "what is the date of the event", "on which day is the workshop", "when will the placement training be held",
        "which date is the exam", "when is the symposium", "date of the programme", "when does the drive happen", "what day is the internal test",
        "when is the guest lecture", "schedule of the event", "when is the placement drive",
    ],
    "event_time": [
        "what time does it start", "at what time is the seminar", "what is the timing", "when does the session begin", "what time will it end",
        "how long is the workshop", "start time of the event", "what time should i reach", "duration of the programme", "timing of the exam",
    ],
    "location": [
        "where is the event", "where will the seminar be held", "what is the venue", "which hall is it", "location of the workshop",
        "where should i go", "which room is the exam", "where is the placement training", "venue details", "where to report",
    ],
    "eligibility": [
        "who can attend", "who is eligible", "who can participate", "can i attend this", "which students are allowed", "is it open to second year",
        "eligibility criteria", "am i eligible for the drive", "which department can join", "who can apply",
    ],
    "deadline": [
        "what is the last date", "when is the deadline", "last date to apply", "by when should i register", "due date for fee payment",
        "when should i submit", "what is the registration deadline", "last date to pay the fee", "until when can i apply", "closing date",
    ],
    "registration": [
        "how do i register", "how to apply", "registration process", "where to register", "is there a registration link", "how can i enroll",
        "how to participate", "what is the application procedure", "registration form", "how to sign up",
    ],
    "contact": [
        "who should i contact", "contact details", "whom to call for queries", "email id of the coordinator", "phone number for help",
        "who is the coordinator", "how can i reach the department", "contact person", "helpline number", "who to ask for doubts",
    ],
    "instructions": [
        "what should i bring", "what do i need to carry", "any instructions", "dress code", "what documents are required", "is id card mandatory",
        "rules to follow", "guidelines for students", "do i need a laptop", "what are the requirements",
    ],
    "fee": [
        "how much is the fee", "what is the registration fee", "amount to be paid", "what are the charges", "fee structure", "how much do i have to pay",
        "is there any fine", "cost of the workshop", "payment details", "exam fee amount",
    ],
    "summary": [
        "tell me about this event", "summarize the circular", "what is this notice about", "give me an overview", "explain the circular",
        "what is the circular about", "describe the programme", "give me the details", "short summary please", "what does this notice say",
    ],
}

_RULES = [
    ("summary", r"\b(summari[sz]e|summary|overview|tell me about|what is this (?:notice|circular|about)|what(?:'s| is) the circular|explain (?:this|the)|describe)\b"),
    ("deadline", r"\b(last date|deadline|due date|cut-?off|by when|till when|until when|last day|closing date|when (?:should|do|must|can|to) (?:i |we |students? )?(?:register|apply|submit|pay|enrol+|enroll))"),
    ("contact", r"\b(contact|phone number|email|e-mail|mail id|whom to|who to (?:call|ask)|helpline|coordinator|call for)\b"),
    ("fee", r"\b(fee|fees|how much|cost|charges?|fine|penalty|amount)\b"),
    ("registration", r"\b(how (?:do|can|to|should)\b.{0,12}\b(?:register|apply|enrol+|enroll|sign up|participate)|registration (?:link|process|procedure|form)|where (?:to|do i|can i) register|register|registration)\b"),
    ("eligibility", r"\b(who can|who is eligible|eligib\w*|can i (?:attend|participate|apply|join)|open to|criteria|which (?:year|students|department|branch)|who all)\b"),
    ("instructions", r"\b(bring|carry|dress|instructions?|documents?|rules|guidelines|requirements?|mandatory|do i need|what should i)\b"),
    ("location", r"\b(where|venue|location|which (?:hall|room|block|lab)|place)\b"),
    ("event_time", r"\b(what time|at what time|timings?|start time|begin|duration|how long|ends?)\b|\btime\b"),
    ("event_date", r"\b(when|date|which day|what day|schedule)\b"),
]

_PIPE = None


def _model():
    global _PIPE
    if _PIPE is None:
        X, y = [], []
        for label, qs in SEED.items():
            for q in qs:
                X.append(q)
                y.append(label)
        _PIPE = make_pipeline(
            TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True),
            LogisticRegression(max_iter=1000, C=8.0),
        )
        _PIPE.fit(X, y)
    return _PIPE


def classify(question: str) -> dict:
    q = question.lower().strip()
    pipe = _model()
    probs = pipe.predict_proba([q])[0]
    ranked = sorted(zip(pipe.classes_, probs), key=lambda x: -x[1])
    model_label, model_conf = ranked[0]
    rule_label = next((lab for lab, rx in _RULES if re.search(rx, q)), None)
    label = rule_label or model_label
    conf = max(float(model_conf), 0.85) if rule_label else float(model_conf)
    if rule_label and rule_label == model_label:
        conf = max(conf, 0.95)
    return {
        "intent": label,
        "label": INTENT_LABELS[label],
        "confidence": round(conf, 3),
        "source": "rules+model" if rule_label else "model",
        "alternatives": [{"intent": c, "confidence": round(float(p), 3)} for c, p in ranked[:3]],
    }


_PRONOUN = re.compile(r"\b(it|this|that|there|they|these|those|the event|the programme|the program|the session|same)\b", re.I)


def is_followup(question: str) -> bool:
    """Short / pronoun-only questions refer to the previous turn ("Where?", "And the time?")."""
    toks = content_tokens(question)
    if len(toks) <= 2:
        return True
    return bool(_PRONOUN.search(question)) and len(toks) <= 4
