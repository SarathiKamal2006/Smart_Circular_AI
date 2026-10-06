const BASE = "/api";

async function req(path, opts = {}) {
  const res = await fetch(BASE + path, opts);
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const j = await res.json();
      msg = j.detail || msg;
    } catch {}
    throw new Error(msg);
  }
  return res.json();
}

export function sessionId() {
  try {
    let id = localStorage.getItem("sca_session");
    if (!id) {
      id = (crypto.randomUUID && crypto.randomUUID()) || String(Date.now()) + Math.random().toString(16).slice(2);
      localStorage.setItem("sca_session", id);
    }
    return id;
  } catch {
    return "anon-session";
  }
}

export const api = {
  stats: () => req("/stats"),
  circulars: () => req("/circulars"),
  circular: (id) => req(`/circulars/${id}`),
  upload: (file) => {
    const fd = new FormData();
    fd.append("file", file);
    return req("/circulars", { method: "POST", body: fd });
  },
  loadSamples: () => req("/circulars/samples/load", { method: "POST" }),
  remove: (id) => req(`/circulars/${id}`, { method: "DELETE" }),
  chat: (question, circular_id) =>
    req("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, circular_id: circular_id || null, session_id: sessionId() }),
    }),
  history: () => req(`/history/${sessionId()}`),
  clearHistory: () => req(`/history/${sessionId()}`, { method: "DELETE" }),
  ttsUrl: (messageId) => `${BASE}/tts/${messageId}`,
};

export function daysUntil(iso) {
  if (!iso) return null;
  const d = new Date(iso + "T00:00:00");
  const t = new Date();
  t.setHours(0, 0, 0, 0);
  return Math.round((d - t) / 86400000);
}

export function countdownLabel(iso) {
  const n = daysUntil(iso);
  if (n === null) return null;
  if (n === 0) return { text: "Today", tone: "hot" };
  if (n === 1) return { text: "Tomorrow", tone: "hot" };
  if (n < 0) return { text: `${-n} day${n === -1 ? "" : "s"} ago`, tone: "past" };
  return { text: `in ${n} days`, tone: n <= 7 ? "hot" : "ok" };
}
