import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { UploadCloud, Loader2, FileText, Trash2, MessageSquareText, Wand2, AlertTriangle, ScanText, Image as ImageIcon } from "lucide-react";
import { api } from "../api.js";
import Facts from "../components/Facts.jsx";
import { Rich } from "./Chat.jsx";

const KIND = { pdf: "PDF text", "pdf+ocr": "PDF + OCR", "image-ocr": "Image OCR", text: "Text", docx: "Word" };

const ENT_LABEL = {
  dates: "Dates", times: "Times", venues: "Venues", departments: "Departments", years: "Years",
  emails: "Emails", phones: "Phones", money: "Amounts", links: "Links", organizations: "Organizations", persons: "People",
};

export default function Upload() {
  const nav = useNavigate();
  const input = useRef(null);
  const [list, setList] = useState([]);
  const [sel, setSel] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [drag, setDrag] = useState(false);
  const [loaded, setLoaded] = useState(false);

  const refresh = useCallback(async (selectId) => {
    const l = await api.circulars();
    setList(l);
    setSel((cur) => l.find((c) => c.id === (selectId ?? cur?.id)) || l[0] || null);
    setLoaded(true);
  }, []);

  useEffect(() => {
    refresh().catch((e) => {
      setError("Cannot reach the backend. Start it with: uvicorn app.main:app --reload (inside /backend)");
      setLoaded(true);
    });
  }, [refresh]);

  async function handleFiles(files) {
    const f = files?.[0];
    if (!f) return;
    setBusy(true);
    setError("");
    try {
      const c = await api.upload(f);
      await refresh(c.id);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
      if (input.current) input.current.value = "";
    }
  }

  async function samples() {
    setBusy(true);
    setError("");
    try {
      await api.loadSamples();
      await refresh();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function remove(id) {
    if (!confirm("Delete this circular?")) return;
    await api.remove(id);
    setSel(null);
    await refresh();
  }

  const ents = sel?.facts?.entities || {};

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1 className="h1">Circulars</h1>
          <p className="muted">Upload a notice — the AI reads it, extracts the key facts and indexes it for chat.</p>
        </div>
        <button className="btn btn-ghost" onClick={samples} disabled={busy}>
          <Wand2 size={16} /> Load sample circulars
        </button>
      </div>

      <div
        className={"dropzone glass" + (drag ? " drag" : "") + (busy ? " busy" : "")}
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          handleFiles(e.dataTransfer.files);
        }}
        onClick={() => !busy && input.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => e.key === "Enter" && input.current?.click()}
      >
        <input ref={input} type="file" hidden accept=".pdf,.png,.jpg,.jpeg,.webp,.bmp,.tif,.tiff,.txt,.docx" onChange={(e) => handleFiles(e.target.files)} />
        {busy ? <Loader2 className="spin" size={30} /> : <UploadCloud size={30} />}
        <div>
          <b>{busy ? "Reading circular… extracting text, entities & embeddings" : "Drop a circular here or click to browse"}</b>
          <small>PDF · scanned image (OCR) · DOCX · TXT — up to 15 MB</small>
        </div>
      </div>

      {error && (
        <div className="alert">
          <AlertTriangle size={16} /> {error}
        </div>
      )}

      <div className="split">
        <aside className="list glass">
          <div className="list-head">Your circulars ({list.length})</div>
          {loaded && list.length === 0 && (
            <div className="empty">
              <FileText size={26} />
              <p>No circulars yet.</p>
              <small>Upload one, or load the four bundled samples to try the chatbot instantly.</small>
            </div>
          )}
          {list.map((c) => (
            <button key={c.id} className={"list-item" + (sel?.id === c.id ? " active" : "")} onClick={() => setSel(c)}>
              <span className="li-icon">{c.kind?.includes("ocr") ? <ScanText size={16} /> : c.kind === "image-ocr" ? <ImageIcon size={16} /> : <FileText size={16} />}</span>
              <span className="li-text">
                <b>{c.title}</b>
                <small>{c.filename}</small>
              </span>
            </button>
          ))}
        </aside>

        <section className="detail">
          {!sel ? (
            <div className="glass empty big">
              <Wand2 size={28} />
              <p>Select a circular to see what the AI understood.</p>
            </div>
          ) : (
            <div className="glass detail-card">
              <div className="detail-top">
                <div>
                  <span className="badge">{KIND[sel.kind] || sel.kind}</span>
                  <h2>{sel.title}</h2>
                  <small className="muted">
                    {sel.filename} · {sel.n_chunks} chunks indexed
                  </small>
                </div>
                <div className="row gap">
                  <button className="btn btn-primary" onClick={() => nav(`/chat?circular=${sel.id}`)}>
                    <MessageSquareText size={16} /> Ask about this
                  </button>
                  <button className="icon-btn danger" onClick={() => remove(sel.id)} aria-label="Delete circular">
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>

              <h4 className="sub">Key facts</h4>
              <Facts facts={sel.facts} />

              <h4 className="sub">AI summary</h4>
              <div className="summary">
                <Rich text={sel.summary} />
              </div>

              <h4 className="sub">Entities detected</h4>
              <div className="ents">
                {Object.keys(ents).length === 0 && <span className="muted small">No entities found.</span>}
                {Object.entries(ents).map(([k, v]) => (
                  <div className="ent-row" key={k}>
                    <span className="ent-k">{ENT_LABEL[k] || k}</span>
                    <div className="chips">
                      {v.slice(0, 6).map((x) => (
                        <span className="chip sm" key={x}>
                          {x}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
