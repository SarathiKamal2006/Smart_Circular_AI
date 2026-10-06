import { useEffect, useState } from "react";
import { NavLink, Link } from "react-router-dom";
import { Home, FileUp, MessageSquareText, History, Sun, Moon, Sparkles } from "lucide-react";

const links = [
  { to: "/", label: "Home", icon: Home, end: true },
  { to: "/upload", label: "Circulars", icon: FileUp },
  { to: "/chat", label: "Chatbot", icon: MessageSquareText },
  { to: "/history", label: "History", icon: History },
];

export default function Navbar() {
  const [theme, setTheme] = useState(() => {
    try {
      return localStorage.getItem("sca_theme") || "dark";
    } catch {
      return "dark";
    }
  });
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem("sca_theme", theme);
    } catch {}
  }, [theme]);

  return (
    <header className="nav">
      <Link to="/" className="brand">
        <span className="brand-mark">
          <Sparkles size={18} />
        </span>
        <span>
          Smart Circular <b>AI</b>
        </span>
      </Link>
      <nav className="nav-links">
        {links.map(({ to, label, icon: Icon, end }) => (
          <NavLink key={to} to={to} end={end} className={({ isActive }) => "nav-link" + (isActive ? " active" : "")}>
            <Icon size={16} />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>
      <button className="icon-btn" onClick={() => setTheme(theme === "dark" ? "light" : "dark")} aria-label="Toggle theme">
        {theme === "dark" ? <Sun size={17} /> : <Moon size={17} />}
      </button>
    </header>
  );
}
