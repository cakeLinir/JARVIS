import { useCallback, useEffect, useState } from "react";
import { getDashboardOverview, logoutDashboard } from "./api/client";
import { ChatPage } from "./pages/ChatPage";
import { DashboardPage } from "./pages/DashboardPage";
import { LoginPage } from "./pages/LoginPage";
import { ShiftsPage } from "./pages/ShiftsPage";
import { StreamingPage } from "./pages/StreamingPage";
import { TodoPage } from "./pages/TodoPage";

type Page = "overview" | "todos" | "shifts" | "streaming" | "chat";

const PAGE_LABELS: Record<Page, string> = {
  overview: "Übersicht",
  todos: "Todos",
  shifts: "Schichtplan",
  streaming: "Streaming",
  chat: "Chat",
};

export default function App() {
  const [authed, setAuthed] = useState<boolean | null>(null); // null = noch unbekannt
  const [page, setPage] = useState<Page>("overview");

  // Prüfe Auth-Status beim Start durch einen leichten API-Call
  const checkAuth = useCallback(async () => {
    try {
      await getDashboardOverview();
      setAuthed(true);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      if (msg === "AUTH_REQUIRED") setAuthed(false);
      else setAuthed(true); // Server erreichbar, anderer Fehler → trotzdem angezeigt
    }
  }, []);

  useEffect(() => { void checkAuth(); }, [checkAuth]);

  async function handleLogout() {
    await logoutDashboard();
    setAuthed(false);
  }

  function handleAuthRequired() {
    setAuthed(false);
  }

  // Lade-Zustand
  if (authed === null) {
    return (
      <div style={{ display: "grid", placeItems: "center", minHeight: "100vh" }}>
        <span className="muted">Verbinde mit JARVIS …</span>
      </div>
    );
  }

  // Login
  if (!authed) {
    return <LoginPage />;
  }

  return (
    <>
      {/* Globale Navigation */}
      <nav className="app-nav">
        <div className="app-nav-brand">⚙ JARVIS</div>
        <div className="app-nav-links">
          {(Object.keys(PAGE_LABELS) as Page[]).map(p => (
            <button
              key={p}
              className={`nav-link ${page === p ? "nav-link-active" : "secondary"}`}
              onClick={() => setPage(p)}
            >
              {PAGE_LABELS[p]}
            </button>
          ))}
        </div>
        <button className="secondary" onClick={handleLogout} style={{ fontSize: 13 }}>
          Abmelden
        </button>
      </nav>

      {/* Seiten */}
      {page === "overview" && <DashboardPage onAuthRequired={handleAuthRequired} />}
      {page === "todos" && <TodoPage onAuthRequired={handleAuthRequired} />}
      {page === "shifts" && <ShiftsPage onAuthRequired={handleAuthRequired} />}
      {page === "streaming" && <StreamingPage onAuthRequired={handleAuthRequired} />}
      {page === "chat" && <ChatPage />}
    </>
  );
}
