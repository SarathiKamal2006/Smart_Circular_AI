"""The conversational RAG pipeline.

question -> follow-up resolution (memory) -> intent -> retrieval (FAISS / TF-IDF) -> circular selection
         -> grounded extractive answer  -> (optional) Gemini rewrite with RAG context -> response
"""
from __future__ import annotations

from .. import db
from . import answer as ans
from . import llm
from .intent import classify, is_followup
from .nlp import content_tokens, extract_entities, suggest_questions
from .retriever import retriever

NOT_FOUND = "I couldn't find that in the circular. Try asking about the date, time, venue, eligibility, deadline or contact."


def refresh_index() -> None:
    retriever.rebuild(db.all_chunks())


def _facts_text(f: dict) -> str:
    lines = [f"Title: {f['title']}"]
    if f.get("department"):
        lines.append(f"Department: {f['department']}")
    if f.get("event_date"):
        lines.append(f"Event date: {f['event_date']['text']}")
    if f.get("time"):
        lines.append(f"Time: {f['time']}")
    if f.get("venue"):
        lines.append(f"Venue: {f['venue']}")
    if f.get("deadline"):
        lines.append(f"Deadline: {f['deadline']['text']} ({f['deadline']['sentence']})")
    return "\n".join(lines)


def ask(question: str, session_id: str, circular_id: int | None = None) -> dict:
    history = db.get_messages(session_id)
    last_ai = next((m for m in reversed(history) if m["role"] == "assistant" and m["circular_id"]), None)

    # 1) conversation memory ------------------------------------------------
    followup = is_followup(question)
    if circular_id is None and followup and last_ai:
        circular_id = last_ai["circular_id"]  # "Where?" keeps talking about the same circular
    context_note = None
    search_q = question
    if followup and last_ai:
        prev_user = next((m for m in reversed(history) if m["role"] == "user" and m["id"] < last_ai["id"]), None)
        if prev_user:
            search_q = f"{prev_user['content']} {question}"
            context_note = prev_user["content"]

    # 2) understanding ------------------------------------------------------
    intent = classify(question)
    q_entities = extract_entities(question)

    # 3) retrieval + circular selection ------------------------------------
    hits = retriever.search(search_q, k=10_000, circular_id=circular_id)
    if not hits:
        return _empty(question, session_id, intent, "Please upload a circular first — then I can answer questions about it.")
    if circular_id is None:
        best: dict[int, float] = {}
        for h in hits:
            best.setdefault(h["circular_id"], h["score"])
        qtok = set(content_tokens(question))
        titles = {c["id"]: set(content_tokens(c["title"])) for c in db.list_circulars()}
        sticky = last_ai["circular_id"] if last_ai else None

        def rank(cid):  # chunk similarity + title-word overlap + small "stay on topic" bonus
            return best[cid] + 0.25 * len(qtok & titles.get(cid, set())) + (0.15 if cid == sticky else 0.0)

        chosen_id = max(best, key=rank)
    else:
        chosen_id = circular_id
    circ = db.get_circular(chosen_id, full=True)
    if not circ:
        return _empty(question, session_id, intent, NOT_FOUND)
    facts = circ["facts"]
    facts["summary"] = circ["summary"]
    chunk_hits = [h for h in hits if h["circular_id"] == chosen_id][:4]
    top_score = chunk_hits[0]["score"] if chunk_hits else 0.0
    weak_intent = intent["source"] == "model" and intent["confidence"] < 0.5

    # 4) grounded answer ----------------------------------------------------
    composed = None if weak_intent else ans.compose(intent["intent"], question, facts, retriever.rank_texts)
    evidence: list[str] = []
    text = None
    if composed and composed[0]:
        text, evidence = composed
        grounded = 1.0
    else:
        fb = ans.best_sentences(search_q, circ["text"], retriever.rank_texts)
        if fb:
            text, evidence, sc = fb
            grounded = min(1.0, 0.5 + sc)
        else:
            text, grounded = NOT_FOUND, 0.15

    # 5) optional Gemini (RAG) ---------------------------------------------
    engine = "extractive-nlp"
    if llm.available() and grounded > 0.2 and not (weak_intent and not (set(content_tokens(question)) & set(content_tokens(circ["text"])))):
        full = circ["text"] if len(circ["text"]) < 3500 else "\n---\n".join(h["text"] for h in chunk_hits)
        g = llm.answer(question, full, _facts_text(facts), history)
        if g:
            text, engine = g, "gemini-rag"

    off_topic = weak_intent and not (set(content_tokens(question)) & set(content_tokens(circ["text"])))
    if off_topic:
        text, grounded, evidence, engine = NOT_FOUND, 0.1, [], "extractive-nlp"
    confidence = round(min(0.99, 0.55 * intent["confidence"] + 0.25 * grounded + 0.2 * min(1.0, top_score * 2)), 3)
    if text == NOT_FOUND:
        confidence = min(confidence, 0.3)

    sources = [{"kind": "evidence", "text": e} for e in evidence[:3]]
    sources += [{"kind": "chunk", "text": h["text"], "score": round(h["score"], 3)} for h in chunk_hits[:3]]

    db.add_message(session_id, "user", question, chosen_id)
    mid = db.add_message(session_id, "assistant", text, chosen_id, intent["intent"], confidence, sources)
    return {
        "message_id": mid,
        "answer": text,
        "intent": intent,
        "confidence": confidence,
        "engine": engine,
        "retriever": retriever.backend,
        "circular_id": chosen_id,
        "circular_title": circ["title"],
        "followup": bool(followup and last_ai),
        "context_from": context_note,
        "question_entities": q_entities,
        "sources": sources,
        "suggestions": suggest_questions(facts),
    }


def _empty(question, session_id, intent, text):
    db.add_message(session_id, "user", question)
    mid = db.add_message(session_id, "assistant", text, None, intent["intent"], 0.1, [])
    return {
        "message_id": mid, "answer": text, "intent": intent, "confidence": 0.1, "engine": "none",
        "retriever": retriever.backend, "circular_id": None, "circular_title": None, "followup": False,
        "context_from": None, "question_entities": {}, "sources": [], "suggestions": [],
    }
