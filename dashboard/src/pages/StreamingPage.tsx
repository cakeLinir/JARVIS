import { useCallback, useEffect, useState } from "react";
import {
    getStreamingAdviceForDate,
    getStreamingAdviceToday,
    getStreamingAdviceTomorrow,
    getStreamingAdviceWeek,
} from "../api/shifts";
import { Panel } from "../components/Panel";
import type { StreamingAdvice } from "../types/shift";
import { SHIFT_TYPE_CLASS, SHIFT_TYPE_LABELS } from "../types/shift";

type Props = { onAuthRequired: () => void };
type Tab = "today" | "tomorrow" | "week" | "custom";

function todayStr(): string { return new Date().toISOString().slice(0, 10); }

function addDays(dateStr: string, n: number): string {
    const d = new Date(`${dateStr}T00:00:00`);
    d.setDate(d.getDate() + n);
    return d.toISOString().slice(0, 10);
}

// ── Empfehlungs-Badge ──────────────────────────────────────────────────────

function RecBadge({ rec }: { rec: StreamingAdvice["recommendation"] }) {
    const map: Record<StreamingAdvice["recommendation"], { label: string; cls: string }> = {
        yes: { label: "✅ Empfohlen", cls: "ok" },
        conditional: { label: "⚠️ Bedingt", cls: "warn" },
        no: { label: "❌ Nicht empfohlen", cls: "bad" },
        unknown: { label: "❓ Unbekannt", cls: "info" },
    };
    const { label, cls } = map[rec] ?? map.unknown;
    return <span className={`badge ${cls} rec-badge`}>{label}</span>;
}

// ── Score-Bar ──────────────────────────────────────────────────────────────

function ScoreBar({ score }: { score: number }) {
    const color = score >= 70 ? "var(--ok)" : score >= 35 ? "var(--warn)" : "var(--bad)";
    return (
        <div className="score-bar-wrap">
            <div className="score-bar-track">
                <div className="score-bar-fill" style={{ width: `${score}%`, background: color }} />
            </div>
            <span className="score-bar-label" style={{ color }}>{score} / 100</span>
        </div>
    );
}

// ── Zeitfenster-Liste ──────────────────────────────────────────────────────

function TimeWindowList({ windows }: { windows: StreamingAdvice["timeWindows"] }) {
    if (windows.length === 0) return null;
    const qClass = { good: "ok", limited: "warn", poor: "bad" } as const;
    return (
        <div className="time-window-list">
            {windows.map((w, i) => (
                <div key={i} className={`time-window-item ${qClass[w.quality]}`}>
                    <span className="time-window-range">{w.start} – {w.end}</span>
                    <span className={`badge ${qClass[w.quality]}`}>{w.label}</span>
                </div>
            ))}
        </div>
    );
}

// ── Einzel-Karte ───────────────────────────────────────────────────────────

function AdviceCard({ advice }: { advice: StreamingAdvice }) {
    const dateLabel = new Date(`${advice.date}T00:00:00`).toLocaleDateString("de-DE", {
        weekday: "long", day: "2-digit", month: "2-digit", year: "numeric",
    });

    return (
        <div className="advice-card panel">
            {/* Kopfzeile */}
            <div className="advice-card-header">
                <div>
                    <div className="advice-date">{dateLabel}</div>
                    {advice.shift && (
                        <span className={`badge ${SHIFT_TYPE_CLASS[advice.shift.type] ?? ""} advice-shift-badge`}>
                            {SHIFT_TYPE_LABELS[advice.shift.type] ?? advice.shift.label}
                            {" · "}{advice.shift.startTime}–{advice.shift.endTime}
                            {advice.shift.overnight ? " +1" : ""}
                        </span>
                    )}
                    {!advice.shift && <span className="muted" style={{ fontSize: 13 }}>Keine Schicht eingetragen</span>}
                </div>
                <RecBadge rec={advice.recommendation} />
            </div>

            {/* Score */}
            <ScoreBar score={advice.score} />

            {/* Stream-Ende */}
            {advice.latestStreamEnd && (
                <div className="advice-stream-end">
                    Spätestes Stream-Ende: <strong>{advice.latestStreamEnd} Uhr</strong>
                </div>
            )}

            {/* Zeitfenster */}
            {advice.timeWindows.length > 0 && (
                <div style={{ marginTop: 12 }}>
                    <div className="advice-section-label">Zeitfenster</div>
                    <TimeWindowList windows={advice.timeWindows} />
                </div>
            )}

            {/* Begründungen */}
            {advice.reasons.length > 0 && (
                <div style={{ marginTop: 12 }}>
                    <div className="advice-section-label">Begründung</div>
                    <ul className="advice-reason-list">
                        {advice.reasons.map((r, i) => <li key={i}>{r}</li>)}
                    </ul>
                </div>
            )}

            {/* Warnungen */}
            {advice.warnings.length > 0 && (
                <div style={{ marginTop: 8 }}>
                    <div className="advice-section-label warn-text">Hinweise</div>
                    <ul className="advice-reason-list advice-warnings">
                        {advice.warnings.map((w, i) => <li key={i}>{w}</li>)}
                    </ul>
                </div>
            )}

            {/* Recovery */}
            {advice.recoveryNeeded && (
                <div className="advice-recovery">
                    ⚕️ Recovery-Tag nach Nachtschicht — Schlaf hat Priorität.
                </div>
            )}
        </div>
    );
}

// ── Hauptkomponente ────────────────────────────────────────────────────────

export function StreamingPage({ onAuthRequired }: Props) {
    const [tab, setTab] = useState<Tab>("today");
    const [customDate, setCustomDate] = useState(todayStr());
    const [advice, setAdvice] = useState<StreamingAdvice | StreamingAdvice[] | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const load = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            if (tab === "today") {
                const res = await getStreamingAdviceToday();
                setAdvice(res.advice);
            } else if (tab === "tomorrow") {
                const res = await getStreamingAdviceTomorrow();
                setAdvice(res.advice);
            } else if (tab === "week") {
                const res = await getStreamingAdviceWeek();
                setAdvice(res.advice);
            } else if (tab === "custom") {
                const res = await getStreamingAdviceForDate(customDate);
                setAdvice(res.advice);
            }
        } catch (e) {
            const msg = e instanceof Error ? e.message : String(e);
            if (msg === "AUTH_REQUIRED") { onAuthRequired(); return; }
            setError(msg);
        } finally {
            setLoading(false);
        }
    }, [tab, customDate, onAuthRequired]);

    useEffect(() => { void load(); }, [load]);

    const adviceList = Array.isArray(advice) ? advice : advice ? [advice] : [];

    // Zusammenfassung für Wochen-Tab
    const weekSummary = Array.isArray(advice) ? {
        yes: advice.filter(a => a.recommendation === "yes").length,
        conditional: advice.filter(a => a.recommendation === "conditional").length,
        no: advice.filter(a => a.recommendation === "no").length,
        unknown: advice.filter(a => a.recommendation === "unknown").length,
    } : null;

    return (
        <div className="dashboard-shell">
            <div className="app-header">
                <div>
                    <h1>Streaming-Empfehlung</h1>
                    <span className="muted">Basierend auf Schichtplan und Arbeitsschutz-Logik</span>
                </div>
                <div className="header-actions">
                    <button className="secondary" onClick={load} disabled={loading}>Aktualisieren</button>
                </div>
            </div>

            <div style={{ padding: "16px 0" }}>
                {error && <div className="error-box">{error}</div>}

                {/* Tab-Navigation */}
                <div className="tab-bar" style={{ marginBottom: 16 }}>
                    {(["today", "tomorrow", "week", "custom"] as Tab[]).map(t => (
                        <button
                            key={t}
                            className={`tab-btn ${tab === t ? "tab-active" : "secondary"}`}
                            onClick={() => setTab(t)}
                        >
                            {{ today: "Heute", tomorrow: "Morgen", week: "7 Tage", custom: "Datum wählen" }[t]}
                        </button>
                    ))}
                </div>

                {/* Datum-Picker für custom */}
                {tab === "custom" && (
                    <div className="form-row" style={{ maxWidth: 280, marginBottom: 16 }}>
                        <label className="form-label">Datum</label>
                        <input
                            className="form-input"
                            type="date"
                            value={customDate}
                            onChange={e => setCustomDate(e.target.value)}
                            min={addDays(todayStr(), -30)}
                            max={addDays(todayStr(), 60)}
                        />
                    </div>
                )}

                {/* Wochen-Zusammenfassung */}
                {tab === "week" && weekSummary && (
                    <div className="metric-grid" style={{ marginBottom: 16 }}>
                        <div className="metric-card">
                            <span className="metric-label">Empfohlen</span>
                            <div className="metric-value text-ok">{weekSummary.yes}</div>
                        </div>
                        <div className="metric-card">
                            <span className="metric-label">Bedingt</span>
                            <div className="metric-value text-warn">{weekSummary.conditional}</div>
                        </div>
                        <div className="metric-card">
                            <span className="metric-label">Nicht empfohlen</span>
                            <div className="metric-value text-bad">{weekSummary.no}</div>
                        </div>
                        <div className="metric-card">
                            <span className="metric-label">Unbekannt</span>
                            <div className="metric-value text-info">{weekSummary.unknown}</div>
                        </div>
                    </div>
                )}

                {loading && <div className="empty">Lädt Empfehlung …</div>}

                {!loading && adviceList.length === 0 && (
                    <div className="empty">Keine Empfehlung verfügbar.</div>
                )}

                {/* Karten */}
                {!loading && adviceList.length > 0 && (
                    <div className={tab === "week" ? "advice-week-grid" : ""}>
                        {adviceList.map(a => (
                            <AdviceCard key={a.date} advice={a} />
                        ))}
                    </div>
                )}

                {/* Hinweis wenn keine Schicht */}
                {!loading && adviceList.some(a => !a.shift) && (
                    <Panel title="Hinweis" style={{ marginTop: 16 }}>
                        <p className="muted" style={{ margin: 0 }}>
                            Für Tage ohne eingetragene Schicht kann JARVIS keine genaue Empfehlung geben.
                            Schichten trägst du ein unter <strong>Schichtplan</strong> oder per Sprache:
                            „Hey Jarvis, morgen habe ich Tagschicht."
                        </p>
                    </Panel>
                )}
            </div>
        </div>
    );
}
