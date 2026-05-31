import { useEffect, useRef, useState } from "react";
import { resetChatHistory, sendChatMessage } from "../api/chat";
import { Panel } from "../components/Panel";

const LS_BASE = "jarvis_agent_base";
const LS_TOKEN = "jarvis_agent_token";
const DEFAULT_BASE = "http://127.0.0.1:8765";

interface Message {
  role: "user" | "jarvis";
  text: string;
  ts: string;
}

function now(): string {
  return new Date().toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
}

export function ChatPage() {
  const [agentBase, setAgentBase] = useState(
    () => localStorage.getItem(LS_BASE) ?? DEFAULT_BASE
  );
  const [token, setToken] = useState(() => localStorage.getItem(LS_TOKEN) ?? "");
  const [showSettings, setShowSettings] = useState(!localStorage.getItem(LS_TOKEN));

  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [speak, setSpeak] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [historyTurns, setHistoryTurns] = useState(0);

  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  function saveSettings() {
    localStorage.setItem(LS_BASE, agentBase);
    localStorage.setItem(LS_TOKEN, token);
    setShowSettings(false);
  }

  async function handleSend() {
    const text = input.trim();
    if (!text || loading) return;

    setInput("");
    setError(null);
    setMessages(prev => [...prev, { role: "user", text, ts: now() }]);
    setLoading(true);

    try {
      const res = await sendChatMessage(text, speak, agentBase, token);
      const answer = res.answer ?? "(kein Text)";
      setMessages(prev => [...prev, { role: "jarvis", text: answer, ts: now() }]);
      setHistoryTurns(res.historyTurns);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  }

  async function handleReset() {
    if (!confirm("Gesprächsgedächtnis wirklich zurücksetzen?")) return;
    try {
      await resetChatHistory(agentBase, token);
      setMessages([]);
      setHistoryTurns(0);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  function handleKey(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void handleSend();
    }
  }

  return (
    <main className="page-content">
      <Panel
        title="JARVIS Chat"
        actions={
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <span className="muted" style={{ fontSize: 12 }}>
              {historyTurns} Runde{historyTurns !== 1 ? "n" : ""}
            </span>
            <button className="secondary" onClick={handleReset} style={{ fontSize: 12 }}>
              Verlauf löschen
            </button>
            <button
              className="secondary"
              onClick={() => setShowSettings(s => !s)}
              style={{ fontSize: 12 }}
              aria-label="Einstellungen"
            >
              ⚙
            </button>
          </div>
        }
      >
        {showSettings && (
          <div
            style={{
              background: "var(--surface-2, #1e1e2e)",
              borderRadius: 8,
              padding: 16,
              marginBottom: 16,
              display: "flex",
              flexDirection: "column",
              gap: 10,
            }}
          >
            <label style={{ fontSize: 13 }}>
              Agent-URL
              <input
                type="text"
                value={agentBase}
                onChange={e => setAgentBase(e.target.value)}
                placeholder="http://127.0.0.1:8765"
                style={{ marginTop: 4, width: "100%" }}
              />
            </label>
            <label style={{ fontSize: 13 }}>
              Token
              <input
                type="password"
                value={token}
                onChange={e => setToken(e.target.value)}
                placeholder="Bearer-Token aus config.local.json"
                style={{ marginTop: 4, width: "100%" }}
              />
            </label>
            <button onClick={saveSettings} style={{ alignSelf: "flex-start" }}>
              Speichern
            </button>
          </div>
        )}

        {/* Chat-Verlauf */}
        <div
          style={{
            minHeight: 320,
            maxHeight: 480,
            overflowY: "auto",
            display: "flex",
            flexDirection: "column",
            gap: 10,
            padding: "4px 0",
          }}
        >
          {messages.length === 0 && (
            <p className="muted" style={{ textAlign: "center", marginTop: 60, fontSize: 14 }}>
              Schreib etwas – JARVIS hört zu.
            </p>
          )}
          {messages.map((m, i) => (
            <div
              key={i}
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: m.role === "user" ? "flex-end" : "flex-start",
              }}
            >
              <div
                style={{
                  maxWidth: "75%",
                  padding: "8px 12px",
                  borderRadius: m.role === "user" ? "12px 12px 2px 12px" : "12px 12px 12px 2px",
                  background:
                    m.role === "user"
                      ? "var(--accent, #7c3aed)"
                      : "var(--surface-2, #1e1e2e)",
                  color: m.role === "user" ? "#fff" : "inherit",
                  fontSize: 14,
                  lineHeight: 1.5,
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                }}
              >
                {m.text}
              </div>
              <span className="muted" style={{ fontSize: 11, marginTop: 2 }}>
                {m.role === "user" ? "Du" : "JARVIS"} · {m.ts}
              </span>
            </div>
          ))}
          {loading && (
            <div style={{ alignSelf: "flex-start" }}>
              <div
                style={{
                  padding: "8px 14px",
                  borderRadius: "12px 12px 12px 2px",
                  background: "var(--surface-2, #1e1e2e)",
                  fontSize: 14,
                  color: "var(--text-muted, #888)",
                }}
              >
                JARVIS denkt …
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {error && (
          <p style={{ color: "var(--red, #f87171)", fontSize: 13, margin: "8px 0 0" }}>
            Fehler: {error}
          </p>
        )}

        {/* Eingabe */}
        <div style={{ display: "flex", gap: 8, marginTop: 12, alignItems: "center" }}>
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKey}
            placeholder="Nachricht eingeben …"
            disabled={loading}
            style={{ flex: 1 }}
            autoFocus
          />
          <button onClick={() => void handleSend()} disabled={loading || !input.trim()}>
            Senden
          </button>
          <label
            style={{ fontSize: 12, display: "flex", alignItems: "center", gap: 4, whiteSpace: "nowrap" }}
            title="Antwort vorlesen lassen"
          >
            <input
              type="checkbox"
              checked={speak}
              onChange={e => setSpeak(e.target.checked)}
            />
            TTS
          </label>
        </div>
      </Panel>
    </main>
  );
}
