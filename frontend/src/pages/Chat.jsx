import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { Send, Mic, Square, Volume2, Loader2, Trash2, ChevronDown, Bot, User, Link2, Zap, FileUp, AudioLines } from "lucide-react";
import { api } from "../api.js";

const DEFAULT_SUGGESTIONS = ["When is it?", "Where will it be held?", "Who can attend?", "What is the last date to register?", "What should I bring?", "Summarize this circular"];

export function Rich({ text }) {
  if (!text) return null;
  const lines = text.split("\n");
  return (
    <div className="rich-text">
      {lines.map((line, li) => {
        const trimmed = line.trim();
        if (!trimmed) return <div key={li} className="rich-gap" />;
        const isBullet = trimmed.startsWith("•") || trimmed.startsWith("- ") || trimmed.startsWith("* ");
        const content = isBullet ? trimmed.replace(/^([•\-*]|\d+\.)\s*/, "") : line;
        const parts = content.split(/(\*\*[^*]+\*\*)/g);
        return (
          <div key={li} className={isBullet ? "rich-bullet" : "rich-line"}>
            {isBullet && <span className="bullet-dot">•</span>}
            <span>
              {parts.map((p, i) => (p.startsWith("**") ? <strong key={i}>{p.slice(2, -2)}</strong> : <span key={i}>{p}</span>))}
            </span>
          </div>
        );
      })}
    </div>
  );
}

function Confidence({ value }) {
  const pct = Math.round((value ?? 0) * 100);
  const tone = pct >= 70 ? "ok" : pct >= 45 ? "mid" : "low";
  return (
    <span className={"conf conf-" + tone} title="Answer confidence">
      <span className="conf-bar">
        <i style={{ width: pct + "%" }} />
      </span>
      {pct}%
    </span>
  );
}

function VoiceButton({ messageId, auto, onAutoDone }) {
  const audio = useRef(null);
  const [state, setState] = useState("idle"); // idle | loading | playing | error

  const play = useCallback(() => {
    if (!audio.current) {
      audio.current = new Audio(api.ttsUrl(messageId));
      audio.current.onended = () => setState("idle");
      audio.current.onerror = () => setState("error");
    }
    setState("loading");
    audio.current.currentTime = 0;
    audio.current.play().then(() => setState("playing")).catch(() => setState("error"));
  }, [messageId]);

  const stop = () => {
    audio.current?.pause();
    setState("idle");
  };

  useEffect(() => {
    if (auto) {
      play();
      onAutoDone?.();
    }
    return () => audio.current?.pause();
    // eslint-disable-next-line
  }, []);

  return (
    <button className={"voice-btn " + state} onClick={state === "playing" ? stop : play} title="Listen to the answer (gTTS)">
      {state === "loading" ? <Loader2 size={14} className="spin" /> : state === "playing" ? <Square size={13} /> : state === "error" ? <AudioLines size={14} /> : <Volume2 size={14} />}
      <span>{state === "playing" ? "Stop" : state === "loading" ? "Preparing…" : state === "error" ? "Voice unavailable" : "Listen"}</span>
    </button>
  );
}

function Message({ m, autoSpeak }) {
  const [open, setOpen] = useState(false);
  if (m.role === "user")
    return (
      <div className="msg user">
        <div className="bubble user">{m.content}</div>
        <span className="avatar u">
          <User size={15} />
        </span>
      </div>
    );
  return (
    <div className="msg bot">
      <span className="avatar b">
        <Bot size={15} />
      </span>
      <div className="bot-col">
        <div className="bubble bot">
          <Rich text={m.content} />
        </div>
        {m.context_from && (
          <div className="ctx">
            <Link2 size={12} /> Follow-up understood in context of “{m.context_from}”
          </div>
        )}
        <div className="meta">
          {m.intent && <span className="intent-chip">{m.intent.label || m.intent}</span>}
          {m.confidence != null && <Confidence value={m.confidence} />}
          {m.engine && (
            <span className="engine">
              <Zap size={11} /> {m.engine === "gemini-rag" ? "Gemini + RAG" : m.engine === "extractive-nlp" ? "NLP extractive" : m.engine}
            </span>
          )}
          <VoiceButton messageId={m.id} auto={autoSpeak && m.fresh} />
          {m.sources?.length > 0 && (
            <button className="src-toggle" onClick={() => setOpen(!open)}>
              Sources <ChevronDown size={13} className={open ? "rot" : ""} />
            </button>
          )}
        </div>
        {open && (
          <div className="sources">
            {m.sources.map((s, i) => (
              <div key={i} className={"source " + s.kind}>
                <span className="src-kind">{s.kind === "evidence" ? "Evidence" : `Retrieved chunk${s.score != null ? ` · ${s.score}` : ""}`}</span>
                {s.text}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default function Chat() {
  const [params] = useSearchParams();
  const [circulars, setCirculars] = useState([]);
  const [cid, setCid] = useState(params.get("circular") ? Number(params.get("circular")) : "");
  const [messages, setMessages] = useState([]);
  const [text, setText] = useState(params.get("q") || "");
  const [busy, setBusy] = useState(false);
  const [suggest, setSuggest] = useState(DEFAULT_SUGGESTIONS);
  const [autoSpeak, setAutoSpeak] = useState(false);
  const [listening, setListening] = useState(false);
  const [error, setError] = useState("");
  const [engine, setEngine] = useState(null);
  const end = useRef(null);
  const recog = useRef(null);

  useEffect(() => {
    api.circulars().then(setCirculars).catch(() => setError("Cannot reach the backend on port 8000."));
    api.history().then((h) => setMessages(h.map((m) => ({ ...m, intent: m.intent ? { label: m.intent.replace("_", " ") } : null })))).catch(() => {});
    api.stats().then((s) => setEngine(s.system)).catch(() => {});
  }, []);

  useEffect(() => {
    const c = circulars.find((x) => x.id === Number(cid));
    if (c?.facts?.suggestions?.length) setSuggest(c.facts.suggestions);
  }, [cid, circulars]);

  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, busy]);

  async function send(q) {
    const question = (q ?? text).trim();
    if (!question || busy) return;
    setText("");
    setError("");
    setBusy(true);
    setMessages((m) => [...m, { id: "tmp" + Date.now(), role: "user", content: question }]);
    try {
      const r = await api.chat(question, cid || null);
      setMessages((m) => [
        ...m,
        {
          id: r.message_id, role: "assistant", content: r.answer, intent: r.intent, confidence: r.confidence, engine: r.engine,
          sources: r.sources, context_from: r.followup ? r.context_from : null, fresh: true,
        },
      ]);
      if (r.suggestions?.length) setSuggest(r.suggestions);
      if (!cid && r.circular_id) api.circulars().then(setCirculars);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  function toggleMic() {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) return setError("Voice input isn't supported in this browser — try Chrome or Edge.");
    if (listening) return recog.current?.stop();
    const r = new SR();
    r.lang = "en-IN";
    r.interimResults = true;
    r.onresult = (e) => setText(Array.from(e.results).map((x) => x[0].transcript).join(""));
    r.onend = () => {
      setListening(false);
    };
    r.onerror = () => setListening(false);
    recog.current = r;
    setListening(true);
    r.start();
  }

  async function clear() {
    if (!confirm("Clear this conversation?")) return;
    await api.clearHistory();
    setMessages([]);
  }

  const current = circulars.find((c) => c.id === Number(cid));

  return (
    <div className="page chat-page">
      <div className="chat glass">
        <div className="chat-top">
          <div className="chat-title">
            <span className="brand-mark sm">
              <Bot size={16} />
            </span>
            <div>
              <b>Smart Circular AI Chatbot</b>
              <small>{engine ? `${engine.retriever} · ${engine.llm.split(" (")[0]}` : "Ask anything about your circulars"}</small>
            </div>
          </div>
          <div className="chat-tools">
            <select value={cid} onChange={(e) => setCid(e.target.value ? Number(e.target.value) : "")} aria-label="Circular to chat with">
              <option value="">All circulars (auto-detect)</option>
              {circulars.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.title.length > 46 ? c.title.slice(0, 44) + "…" : c.title}
                </option>
              ))}
            </select>
            <label className="switch" title="Read every answer aloud">
              <input type="checkbox" checked={autoSpeak} onChange={(e) => setAutoSpeak(e.target.checked)} />
              <span />
              <small>Auto-speak</small>
            </label>
            <button className="icon-btn" onClick={clear} aria-label="Clear conversation" title="Clear conversation">
              <Trash2 size={16} />
            </button>
          </div>
        </div>

        <div className="chat-body">
          {messages.length === 0 && (
            <div className="chat-empty">
              <div className="orb" />
              <h3>{circulars.length ? "Ask me anything about your circulars" : "Upload a circular to begin"}</h3>
              <p className="muted">
                {circulars.length
                  ? current ? `Chatting with “${current.title}”.` : "I'll automatically pick the right circular for your question."
                  : "I answer from the real contents of the notices you upload."}
              </p>
              {!circulars.length && (
                <Link to="/upload" className="btn btn-primary">
                  <FileUp size={16} /> Go to circulars
                </Link>
              )}
            </div>
          )}
          {messages.map((m) => (
            <Message key={m.id} m={m} autoSpeak={autoSpeak} />
          ))}
          {busy && (
            <div className="msg bot">
              <span className="avatar b">
                <Bot size={15} />
              </span>
              <div className="bubble bot">
                <div className="typing">
                  <i />
                  <i />
                  <i />
                </div>
              </div>
            </div>
          )}
          {error && <div className="alert">{error}</div>}
          <div ref={end} />
        </div>

        {circulars.length > 0 && (
          <div className="suggest">
            {suggest.map((s) => (
              <button key={s} className="chip action" onClick={() => send(s)} disabled={busy}>
                {s}
              </button>
            ))}
          </div>
        )}

        <form
          className="composer"
          onSubmit={(e) => {
            e.preventDefault();
            send();
          }}
        >
          <button type="button" className={"icon-btn mic" + (listening ? " on" : "")} onClick={toggleMic} aria-label="Voice input" title="Speak your question">
            <Mic size={18} />
          </button>
          <input value={text} onChange={(e) => setText(e.target.value)} placeholder={listening ? "Listening…" : "Type your question…  e.g. “When is the placement training?”"} aria-label="Your question" />
          <button className="send" disabled={busy || !text.trim()} aria-label="Send">
            {busy ? <Loader2 size={18} className="spin" /> : <Send size={18} />}
          </button>
        </form>
      </div>
    </div>
  );
}
