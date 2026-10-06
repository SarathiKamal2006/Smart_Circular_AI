"""Smart Circular AI – FastAPI application."""
from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config, db
from .services import chat, extract, llm, nlp, tts
from .services.retriever import retriever

app = FastAPI(title="Smart Circular AI", version="2.0.0")
app.add_middleware(
    CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"], allow_credentials=True
)


@app.on_event("startup")
def _startup():
    db.init_db()
    chat.refresh_index()


# ----------------------------------------------------------- ingestion
def _ingest(text: str, filename: str, kind: str) -> dict:
    text = nlp.clean_text(text)
    if len(text) < 20:
        raise HTTPException(422, "Could not read any text from this file.")
    facts = nlp.build_facts(text, filename)
    summary = llm.summarize(text) if llm.available() else None
    summary = summary or nlp.summarize(text)
    facts["suggestions"] = nlp.suggest_questions(facts)
    cid = db.add_circular(facts["title"], filename, kind, text, summary, facts, nlp.chunk_text(text))
    chat.refresh_index()
    return db.get_circular(cid)


@app.post("/api/circulars")
async def upload_circular(file: UploadFile = File(...)):
    suffix = Path(file.filename or "upload.txt").suffix.lower()
    dest = config.UPLOAD_DIR / f"{uuid.uuid4().hex}{suffix}"
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    if dest.stat().st_size > config.MAX_UPLOAD_MB * 1024 * 1024:
        dest.unlink(missing_ok=True)
        raise HTTPException(413, f"File larger than {config.MAX_UPLOAD_MB} MB")
    try:
        text, kind = extract.extract(dest)
    except extract.ExtractionError as e:
        raise HTTPException(422, str(e))
    return _ingest(text, file.filename or dest.name, kind)


@app.get("/api/circulars")
def list_circulars():
    return db.list_circulars()


@app.get("/api/circulars/{cid}")
def get_circular(cid: int):
    c = db.get_circular(cid, full=True)
    if not c:
        raise HTTPException(404, "Circular not found")
    return c


@app.delete("/api/circulars/{cid}")
def delete_circular(cid: int):
    db.delete_circular(cid)
    chat.refresh_index()
    return {"ok": True}


@app.post("/api/circulars/samples/load")
def load_samples():
    """Load the bundled demo circulars (skips ones already present)."""
    have = {c["filename"] for c in db.list_circulars()}
    added = []
    for p in sorted(config.SAMPLE_DIR.glob("*.txt")):
        if p.name in have:
            continue
        added.append(_ingest(p.read_text(encoding="utf-8"), p.name, "text"))
    return {"added": len(added), "circulars": db.list_circulars()}


# ---------------------------------------------------------------- chat
class ChatIn(BaseModel):
    question: str
    session_id: str
    circular_id: int | None = None


@app.post("/api/chat")
def chat_endpoint(body: ChatIn):
    q = body.question.strip()
    if not q:
        raise HTTPException(422, "Empty question")
    return chat.ask(q, body.session_id, body.circular_id)


@app.get("/api/history/{session_id}")
def history(session_id: str):
    return db.get_messages(session_id)


@app.delete("/api/history/{session_id}")
def clear_history(session_id: str):
    db.clear_messages(session_id)
    return {"ok": True}


@app.get("/api/tts/{message_id}")
def tts_message(message_id: int, lang: str = "en"):
    m = db.get_message(message_id)
    if not m:
        raise HTTPException(404, "Message not found")
    try:
        path = tts.speak(m["content"], lang)
    except Exception as e:
        raise HTTPException(503, f"Text-to-speech unavailable: {e}")
    return FileResponse(path, media_type="audio/mpeg")


@app.get("/api/tts")
def tts_text(text: str, lang: str = "en"):
    try:
        path = tts.speak(text, lang)
    except Exception as e:
        raise HTTPException(503, f"Text-to-speech unavailable: {e}")
    return FileResponse(path, media_type="audio/mpeg")


@app.get("/api/stats")
def stats():
    s = db.stats()
    s["system"] = {
        "retriever": retriever.backend,
        "llm": f"Gemini ({config.GEMINI_MODEL})" if llm.available() else "Extractive NLP (add GEMINI_API_KEY for Gemini)",
        "ocr": extract.ocr_available(),
    }
    return s


@app.get("/api/health")
def health():
    return {"status": "ok"}


# Serve the built React app when present (single-server deployment, with SPA fallback for /chat, /upload ...)
_dist = config.BASE_DIR.parent / "frontend" / "dist"
if _dist.exists():
    app.mount("/assets", StaticFiles(directory=_dist / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(404, "Not found")
        f = (_dist / full_path).resolve()
        if full_path and f.is_file() and _dist.resolve() in f.parents:
            return FileResponse(f)
        return FileResponse(_dist / "index.html")
