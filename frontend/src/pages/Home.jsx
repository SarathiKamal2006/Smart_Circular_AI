import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  FileUp, ArrowRight, Cpu, Waves,
} from "lucide-react";
import { api } from "../api.js";

const DEMO = [
  { r: "u", t: "When is the placement training?" },
  { r: "b", t: "The placement training programme is on 15 October 2026 at 10:00 AM in Seminar Hall 2." },
  { r: "u", t: "Where?" },
  { r: "b", t: "It will be held at Seminar Hall 2." },
  { r: "u", t: "What's the last date to register?" },
  { r: "b", t: "The registration deadline is 12 October 2026." },
];

function Stat({ value, label }) {
  return (
    <div className="stat">
      <b>{value}</b>
      <span>{label}</span>
    </div>
  );
}

export default function Home() {
  const [stats, setStats] = useState(null);
  const [shown, setShown] = useState(1);

  useEffect(() => {
    api.stats().then(setStats).catch(() => setStats(null));
  }, []);
  useEffect(() => {
    if (shown >= DEMO.length) return;
    const id = setTimeout(() => setShown((n) => n + 1), 1300);
    return () => clearTimeout(id);
  }, [shown]);

  return (
    <div className="page home">
      <section className="hero">
        <div className="hero-copy">
          <span className="eyebrow">
            <Cpu size={14} /> NLP · RAG · FAISS · Gemini · gTTS
          </span>
          <h1>
            Stop reading circulars.
            <br />
            <span className="grad">Just ask them.</span>
          </h1>
          <p className="lead">
            Upload any college circular — PDF, scan or text — and chat with it in plain English. Smart Circular AI finds the exact detail you need
            and can read the answer aloud.
          </p>
          <div className="cta">
            <Link to="/upload" className="btn btn-primary">
              <FileUp size={17} /> Upload circular
            </Link>
            <Link to="/chat" className="btn btn-ghost">
              Start chat <ArrowRight size={16} />
            </Link>
          </div>
          <div className="stats">
            <Stat value={stats ? stats.circulars : "–"} label="circulars" />
            <Stat value={stats ? stats.questions : "–"} label="questions answered" />
            <Stat value={stats?.avg_confidence != null ? Math.round(stats.avg_confidence * 100) + "%" : "–"} label="avg confidence" />
          </div>
        </div>

        <div className="demo glass" aria-label="Example conversation">
          <div className="demo-head">
            <span className="dot r" />
            <span className="dot y" />
            <span className="dot g" />
            <span className="demo-title">placement_notice.pdf</span>
          </div>
          <div className="demo-body">
            {DEMO.slice(0, shown).map((m, i) => (
              <div key={i} className={"bubble " + (m.r === "u" ? "user" : "bot") + " pop"}>
                {m.t}
                {m.r === "b" && (
                  <span className="demo-voice">
                    <Waves size={13} /> Play voice
                  </span>
                )}
              </div>
            ))}
            {shown < DEMO.length && (
              <div className="typing">
                <i />
                <i />
                <i />
              </div>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}
