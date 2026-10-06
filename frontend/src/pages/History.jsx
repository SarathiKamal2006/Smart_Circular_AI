import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Search, Trash2, MessageSquareText, History as HistoryIcon, RotateCcw } from "lucide-react";
import { api } from "../api.js";

function pairUp(messages) {
  const out = [];
  for (let i = 0; i < messages.length; i++) {
    const m = messages[i];
    if (m.role === "user") {
      const a = messages[i + 1]?.role === "assistant" ? messages[i + 1] : null;
      out.push({ q: m, a });
    }
  }
  return out.reverse();
}

export default function History() {
  const [msgs, setMsgs] = useState([]);
  const [circulars, setCirculars] = useState([]);
  const [filter, setFilter] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([api.history(), api.circulars()])
      .then(([h, c]) => {
        setMsgs(h);
        setCirculars(c);
      })
      .catch(() => setError("Cannot reach the backend."));
  }, []);

  const titles = useMemo(() => Object.fromEntries(circulars.map((c) => [c.id, c.title])), [circulars]);
  const pairs = useMemo(() => pairUp(msgs).filter((p) => !filter || (p.q.content + (p.a?.content || "")).toLowerCase().includes(filter.toLowerCase())), [msgs, filter]);
  const groups = useMemo(() => {
    const g = new Map();
    pairs.forEach((p) => {
      const key = p.a?.circular_id ?? p.q.circular_id ?? 0;
      if (!g.has(key)) g.set(key, []);
      g.get(key).push(p);
    });
    return [...g.entries()];
  }, [pairs]);

  async function clear() {
    if (!confirm("Delete all questions and answers?")) return;
    await api.clearHistory();
    setMsgs([]);
  }

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1 className="h1">History</h1>
          <p className="muted">Every question you asked and the answer you got, grouped by circular.</p>
        </div>
        <button className="btn btn-ghost danger" onClick={clear} disabled={!msgs.length}>
          <Trash2 size={16} /> Clear all
        </button>
      </div>

      <div className="searchbar glass">
        <Search size={16} />
        <input value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="Search questions and answers…" aria-label="Search history" />
      </div>
      {error && <div className="alert">{error}</div>}

      {pairs.length === 0 && !error && (
        <div className="glass empty big">
          <HistoryIcon size={28} />
          <p>{filter ? "Nothing matches your search." : "No conversations yet."}</p>
          {!filter && (
            <Link className="btn btn-primary" to="/chat">
              <MessageSquareText size={16} /> Start chatting
            </Link>
          )}
        </div>
      )}

      {groups.map(([id, items]) => (
        <section key={id} className="hist-group">
          <h3 className="hist-title">{titles[id] || "General questions"} <span className="muted">· {items.length}</span></h3>
          {items.map(({ q, a }) => (
            <article key={q.id} className="hist-card glass">
              <div className="hist-time">{new Date(q.created_at).toLocaleString()}</div>
              <p className="hist-q">{q.content}</p>
              {a && <p className="hist-a">{a.content}</p>}
              <div className="hist-foot">
                {a?.intent && <span className="intent-chip">{a.intent.replace("_", " ")}</span>}
                {a?.confidence != null && <span className="muted small">{Math.round(a.confidence * 100)}% confidence</span>}
                <Link className="replay" to={`/chat?${id ? `circular=${id}&` : ""}q=${encodeURIComponent(q.content)}`}>
                  <RotateCcw size={13} /> Ask again
                </Link>
              </div>
            </article>
          ))}
        </section>
      ))}
    </div>
  );
}
