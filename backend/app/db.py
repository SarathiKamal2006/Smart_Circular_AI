"""SQLite persistence: circulars, chunks and chat messages."""
import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone

from .config import DB_PATH

_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS circulars (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    filename TEXT,
    kind TEXT,
    text TEXT NOT NULL,
    summary TEXT,
    facts_json TEXT,
    n_chunks INTEGER DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    circular_id INTEGER NOT NULL REFERENCES circulars(id) ON DELETE CASCADE,
    idx INTEGER NOT NULL,
    text TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    circular_id INTEGER,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    intent TEXT,
    confidence REAL,
    sources_json TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def conn():
    with _lock:
        c = sqlite3.connect(DB_PATH, check_same_thread=False)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys = ON")
        try:
            yield c
            c.commit()
        finally:
            c.close()


def init_db() -> None:
    with conn() as c:
        c.executescript(SCHEMA)


# ---------------------------------------------------------------- circulars
def add_circular(title, filename, kind, text, summary, facts, chunks) -> int:
    with conn() as c:
        cur = c.execute(
            "INSERT INTO circulars(title, filename, kind, text, summary, facts_json, n_chunks, created_at)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (title, filename, kind, text, summary, json.dumps(facts), len(chunks), now()),
        )
        cid = cur.lastrowid
        c.executemany(
            "INSERT INTO chunks(circular_id, idx, text) VALUES (?,?,?)",
            [(cid, i, t) for i, t in enumerate(chunks)],
        )
        return cid


def _circ(row, full=False):
    d = {
        "id": row["id"],
        "title": row["title"],
        "filename": row["filename"],
        "kind": row["kind"],
        "summary": row["summary"],
        "n_chunks": row["n_chunks"],
        "created_at": row["created_at"],
        "facts": json.loads(row["facts_json"] or "{}"),
    }
    if full:
        d["text"] = row["text"]
    return d


def list_circulars():
    with conn() as c:
        rows = c.execute("SELECT * FROM circulars ORDER BY id DESC").fetchall()
        return [_circ(r) for r in rows]


def get_circular(cid: int, full=False):
    with conn() as c:
        r = c.execute("SELECT * FROM circulars WHERE id=?", (cid,)).fetchone()
        return _circ(r, full) if r else None


def delete_circular(cid: int) -> None:
    with conn() as c:
        c.execute("DELETE FROM chunks WHERE circular_id=?", (cid,))
        c.execute("DELETE FROM circulars WHERE id=?", (cid,))


def all_chunks():
    with conn() as c:
        rows = c.execute("SELECT id, circular_id, idx, text FROM chunks ORDER BY circular_id, idx").fetchall()
        return [dict(r) for r in rows]


# ----------------------------------------------------------------- messages
def add_message(session_id, role, content, circular_id=None, intent=None, confidence=None, sources=None) -> int:
    with conn() as c:
        cur = c.execute(
            "INSERT INTO messages(session_id, circular_id, role, content, intent, confidence, sources_json, created_at)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (session_id, circular_id, role, content, intent, confidence, json.dumps(sources or []), now()),
        )
        return cur.lastrowid


def _msg(r):
    return {
        "id": r["id"],
        "session_id": r["session_id"],
        "circular_id": r["circular_id"],
        "role": r["role"],
        "content": r["content"],
        "intent": r["intent"],
        "confidence": r["confidence"],
        "sources": json.loads(r["sources_json"] or "[]"),
        "created_at": r["created_at"],
    }


def get_messages(session_id, limit=500):
    with conn() as c:
        rows = c.execute(
            "SELECT * FROM messages WHERE session_id=? ORDER BY id ASC LIMIT ?", (session_id, limit)
        ).fetchall()
        return [_msg(r) for r in rows]


def get_message(mid: int):
    with conn() as c:
        r = c.execute("SELECT * FROM messages WHERE id=?", (mid,)).fetchone()
        return _msg(r) if r else None


def clear_messages(session_id) -> None:
    with conn() as c:
        c.execute("DELETE FROM messages WHERE session_id=?", (session_id,))


def stats():
    with conn() as c:
        n_c = c.execute("SELECT COUNT(*) FROM circulars").fetchone()[0]
        n_q = c.execute("SELECT COUNT(*) FROM messages WHERE role='user'").fetchone()[0]
        avg = c.execute("SELECT AVG(confidence) FROM messages WHERE role='assistant' AND confidence IS NOT NULL").fetchone()[0]
        rows = c.execute(
            "SELECT intent, COUNT(*) n FROM messages WHERE role='assistant' AND intent IS NOT NULL GROUP BY intent ORDER BY n DESC"
        ).fetchall()
        return {
            "circulars": n_c,
            "questions": n_q,
            "avg_confidence": round(avg, 3) if avg is not None else None,
            "intents": {r["intent"]: r["n"] for r in rows},
        }
