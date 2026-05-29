import { useCallback, useEffect, useState } from "react";
import { deleteShift, getShifts, upsertShift } from "../api/shifts";
import { Panel } from "../components/Panel";
import type { Shift, ShiftType } from "../types/shift";
import { SHIFT_TYPE_CLASS, SHIFT_TYPE_LABELS, SHIFT_TYPE_TIMES } from "../types/shift";

type Props = { onAuthRequired: () => void };

// ── Helpers ────────────────────────────────────────────────────────────────

function addDays(dateStr: string, n: number): string {
    const d = new Date(`${dateStr}T00:00:00`);
    d.setDate(d.getDate() + n);
    return d.toISOString().slice(0, 10);
}

function todayStr(): string {
    return new Date().toISOString().slice(0, 10);
}

/** Montag der Woche in der das Datum liegt */
function weekStart(dateStr: string): string {
    const d = new Date(`${dateStr}T00:00:00`);
    const day = d.getDay(); // 0=So
    const diff = day === 0 ? -6 : 1 - day;
    d.setDate(d.getDate() + diff);
    return d.toISOString().slice(0, 10);
}

function fmtWeekday(dateStr: string): string {
    return new Date(`${dateStr}T00:00:00`).toLocaleDateString("de-DE", {
        weekday: "short", day: "2-digit", month: "2-digit",
    });
}

const SHIFT_TYPES: ShiftType[] = ["tag", "nacht", "frei", "fakt_frueh", "fakt_spaet"];

// ── Schicht-Badge ──────────────────────────────────────────────────────────

function ShiftBadge({ shift }: { shift: Shift }) {
    return (
        <div className={`shift-badge ${SHIFT_TYPE_CLASS[shift.type as ShiftType] ?? ""}`}>
            <span className="shift-badge-label">{shift.label}</span>
            <span className="shift-badge-time">{shift.startTime}–{shift.endTime}</span>
        </div>
    );
}

// ── Schicht-Eintrag-Popover ────────────────────────────────────────────────

function ShiftEntryForm({ date, existing, onSaved, onDeleted, onCancel }: {
    date: string;
    existing: Shift | null;
    onSaved: (shift: Shift) => void;
    onDeleted?: () => void;
    onCancel: () => void;
}) {
    const [type, setType] = useState<ShiftType>(existing?.type ?? "tag");
    const [notes, setNotes] = useState(existing?.notes ?? "");
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);

    async function handleSave() {
        setSaving(true);
        setError(null);
        try {
            const res = await upsertShift({ date, type, notes: notes || undefined, source: "dashboard" });
            onSaved(res.shift!);
        } catch (e) {
            setError(e instanceof Error ? e.message : String(e));
        } finally {
            setSaving(false);
        }
    }

    async function handleDelete() {
        if (!existing) return;
        setSaving(true);
        try {
            await deleteShift(existing.id);
            onDeleted?.();
        } catch (e) {
            setError(e instanceof Error ? e.message : String(e));
        } finally {
            setSaving(false);
        }
    }

    return (
        <div className="shift-entry-form panel">
            <div className="panel-heading">
                <h2 style={{ fontSize: 15 }}>
                    {fmtWeekday(date)} — {existing ? "Schicht ändern" : "Schicht eintragen"}
                </h2>
                <button className="secondary" style={{ padding: "4px 8px" }} onClick={onCancel}>✕</button>
            </div>
            {error && <div className="error-box">{error}</div>}

            <div className="shift-type-grid">
                {SHIFT_TYPES.map(t => (
                    <button
                        key={t}
                        className={`shift-type-btn ${SHIFT_TYPE_CLASS[t]} ${type === t ? "selected" : ""}`}
                        onClick={() => setType(t)}
                        type="button"
                    >
                        <span className="shift-type-btn-label">{SHIFT_TYPE_LABELS[t]}</span>
                        <span className="shift-type-btn-time">{SHIFT_TYPE_TIMES[t]}</span>
                    </button>
                ))}
            </div>

            <div className="form-row" style={{ marginTop: 10 }}>
                <label className="form-label">Notiz (optional)</label>
                <input
                    className="form-input"
                    value={notes}
                    onChange={e => setNotes(e.target.value)}
                    placeholder="z.B. Vertretung, Tausch …"
                    maxLength={300}
                />
            </div>

            <div className="form-actions" style={{ marginTop: 12 }}>
                <button onClick={handleSave} disabled={saving}>{saving ? "Wird gespeichert …" : "Speichern"}</button>
                {existing && (
                    <button className="btn-danger" onClick={handleDelete} disabled={saving}>Löschen</button>
                )}
                <button className="secondary" onClick={onCancel}>Abbrechen</button>
            </div>
        </div>
    );
}

// ── Hauptkomponente ────────────────────────────────────────────────────────

export function ShiftsPage({ onAuthRequired }: Props) {
    const [refDate, setRefDate] = useState(weekStart(todayStr()));
    const [shifts, setShifts] = useState<Shift[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [activeDate, setActiveDate] = useState<string | null>(null);

    // 4 Wochen laden für Kalenderdarstellung
    const from = addDays(refDate, -7);
    const to = addDays(refDate, 27);

    const load = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await getShifts(from, to);
            setShifts(res.shifts);
        } catch (e) {
            const msg = e instanceof Error ? e.message : String(e);
            if (msg === "AUTH_REQUIRED") { onAuthRequired(); return; }
            setError(msg);
        } finally {
            setLoading(false);
        }
    }, [from, to, onAuthRequired]);

    useEffect(() => { void load(); }, [load]);

    function shiftForDate(date: string): Shift | null {
        return shifts.find(s => s.date === date) ?? null;
    }

    // Kalender: 4 Wochen ab refDate
    const weeks: string[][] = Array.from({ length: 4 }, (_, wi) =>
        Array.from({ length: 7 }, (_, di) => addDays(refDate, wi * 7 + di))
    );

    const today = todayStr();

    function handleSaved(shift: Shift) {
        setShifts(prev => {
            const without = prev.filter(s => s.date !== shift.date);
            return [...without, shift].sort((a, b) => a.date.localeCompare(b.date));
        });
        setActiveDate(null);
    }

    function handleDeleted(date: string) {
        setShifts(prev => prev.filter(s => s.date !== date));
        setActiveDate(null);
    }

    // Statistiken für sichtbaren Zeitraum
    const visibleShifts = shifts.filter(s => s.date >= refDate && s.date <= addDays(refDate, 27));
    const stats = {
        tag: visibleShifts.filter(s => s.type === "tag").length,
        nacht: visibleShifts.filter(s => s.type === "nacht").length,
        frei: visibleShifts.filter(s => s.type === "frei").length,
        fakt_frueh: visibleShifts.filter(s => s.type === "fakt_frueh").length,
        fakt_spaet: visibleShifts.filter(s => s.type === "fakt_spaet").length,
    };

    return (
        <div className="dashboard-shell">
            <div className="app-header">
                <div>
                    <h1>Schichtplan</h1>
                    <span className="muted">{loading ? "Lädt …" : `${shifts.length} Schichten gespeichert`}</span>
                </div>
                <div className="header-actions">
                    <button className="secondary" onClick={() => setRefDate(weekStart(today))}>Heute</button>
                    <button className="secondary" onClick={() => setRefDate(addDays(refDate, -28))}>◀ 4 Wochen</button>
                    <button className="secondary" onClick={() => setRefDate(addDays(refDate, 28))}>4 Wochen ▶</button>
                    <button className="secondary" onClick={load} disabled={loading}>Aktualisieren</button>
                </div>
            </div>

            <div style={{ padding: "16px 0" }}>
                {error && <div className="error-box">{error}</div>}

                {/* Monats-Statistiken */}
                <div className="metric-grid" style={{ marginBottom: 16 }}>
                    {(Object.entries(stats) as [ShiftType, number][]).map(([type, count]) => (
                        <div key={type} className={`metric-card shift-stat-card ${SHIFT_TYPE_CLASS[type]}`}>
                            <span className="metric-label">{SHIFT_TYPE_LABELS[type]}</span>
                            <div className="metric-value">{count}</div>
                            <span className="metric-hint">{SHIFT_TYPE_TIMES[type]}</span>
                        </div>
                    ))}
                </div>

                {/* Kalender */}
                <Panel title="4-Wochen-Übersicht" actions={
                    <span className="muted" style={{ fontSize: 13 }}>
                        {new Date(`${refDate}T00:00:00`).toLocaleDateString("de-DE", { month: "long", year: "numeric" })}
                    </span>
                }>
                    {/* Wochentag-Header */}
                    <div className="cal-header">
                        {["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"].map(d => (
                            <div key={d} className="cal-header-cell">{d}</div>
                        ))}
                    </div>

                    {/* Wochen */}
                    {weeks.map((week, wi) => (
                        <div key={wi} className="cal-week">
                            {week.map(date => {
                                const shift = shiftForDate(date);
                                const isToday = date === today;
                                const isPast = date < today;
                                const isActive = date === activeDate;
                                return (
                                    <div
                                        key={date}
                                        className={[
                                            "cal-cell",
                                            isToday ? "cal-today" : "",
                                            isPast ? "cal-past" : "",
                                            isActive ? "cal-active" : "",
                                        ].join(" ").trim()}
                                        onClick={() => setActiveDate(isActive ? null : date)}
                                        title={shift ? shift.label : "Keine Schicht — klicken zum Eintragen"}
                                    >
                                        <span className="cal-cell-date">{date.slice(8)}</span>
                                        {shift ? (
                                            <ShiftBadge shift={shift} />
                                        ) : (
                                            <span className="cal-cell-empty">+</span>
                                        )}
                                    </div>
                                );
                            })}
                        </div>
                    ))}
                </Panel>

                {/* Schicht-Eintrag-Form */}
                {activeDate && (
                    <div style={{ marginTop: 16 }}>
                        <ShiftEntryForm
                            date={activeDate}
                            existing={shiftForDate(activeDate)}
                            onSaved={handleSaved}
                            onDeleted={() => handleDeleted(activeDate)}
                            onCancel={() => setActiveDate(null)}
                        />
                    </div>
                )}

                {/* Schicht-Liste */}
                <Panel title="Eingetragene Schichten" actions={
                    <span className="muted" style={{ fontSize: 13 }}>{visibleShifts.length} im angezeigten Zeitraum</span>
                }>
                    {visibleShifts.length === 0 ? (
                        <div className="empty">Keine Schichten in diesem Zeitraum eingetragen.</div>
                    ) : (
                        <div className="table-wrap">
                            <table>
                                <thead>
                                    <tr>
                                        <th>Datum</th>
                                        <th>Wochentag</th>
                                        <th>Schicht</th>
                                        <th>Zeit</th>
                                        <th>Quelle</th>
                                        <th>Notiz</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {visibleShifts.map(s => (
                                        <tr
                                            key={s.id}
                                            className={s.date === today ? "cal-today-row" : ""}
                                            style={{ cursor: "pointer" }}
                                            onClick={() => setActiveDate(activeDate === s.date ? null : s.date)}
                                        >
                                            <td>{s.date}</td>
                                            <td>{new Date(`${s.date}T00:00:00`).toLocaleDateString("de-DE", { weekday: "long" })}</td>
                                            <td>
                                                <span className={`badge shift-inline-badge ${SHIFT_TYPE_CLASS[s.type as ShiftType] ?? ""}`}>
                                                    {s.label}
                                                </span>
                                            </td>
                                            <td className="muted">{s.startTime}–{s.endTime}{s.overnight ? " +1" : ""}</td>
                                            <td className="muted">{s.source}</td>
                                            <td className="muted">{s.notes ?? "—"}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </Panel>
            </div>
        </div>
    );
}
