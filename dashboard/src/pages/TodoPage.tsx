import { useCallback, useEffect, useRef, useState } from "react";
import {
    completeTodo,
    createTodo,
    deleteTodo,
    getTodos,
    updateTodo,
} from "../api/todos";
import { Panel } from "../components/Panel";
import { StatusBadge } from "../components/StatusBadge";
import type { Todo, TodoPriority, TodoStatus } from "../types/todo";
import {
    CATEGORY_OPTIONS,
    PRIORITY_COLORS,
    PRIORITY_LABELS,
    STATUS_LABELS,
} from "../types/todo";

type Props = { onAuthRequired: () => void };

// ── Helpers ────────────────────────────────────────────────────────────────

function fmtDate(v?: string | null) {
    if (!v) return "—";
    return new Date(`${v}T00:00:00`).toLocaleDateString("de-DE", {
        day: "2-digit", month: "2-digit", year: "numeric",
    });
}

function isOverdue(todo: Todo): boolean {
    if (!todo.dueDate || todo.status === "done" || todo.status === "cancelled") return false;
    return todo.dueDate < new Date().toISOString().slice(0, 10);
}

function today(): string {
    return new Date().toISOString().slice(0, 10);
}

// ── Kleines Modal ──────────────────────────────────────────────────────────

function Modal({ title, onClose, children }: {
    title: string;
    onClose: () => void;
    children: React.ReactNode;
}) {
    const ref = useRef<HTMLDivElement>(null);
    useEffect(() => {
        function handle(e: KeyboardEvent) { if (e.key === "Escape") onClose(); }
        window.addEventListener("keydown", handle);
        return () => window.removeEventListener("keydown", handle);
    }, [onClose]);

    return (
        <div className="modal-overlay" onClick={e => { if (e.target === ref.current) onClose(); }}>
            <div className="modal-box" ref={ref} onClick={e => e.stopPropagation()}>
                <div className="modal-header">
                    <span className="modal-title">{title}</span>
                    <button className="secondary" onClick={onClose} aria-label="Schließen">✕</button>
                </div>
                {children}
            </div>
        </div>
    );
}

// ── Create-Form ────────────────────────────────────────────────────────────

type CreateFormState = {
    title: string;
    description: string;
    dueDate: string;
    dueTime: string;
    priority: string;
    category: string;
    reminderMinutes: string;
};

const EMPTY_FORM: CreateFormState = {
    title: "", description: "", dueDate: "", dueTime: "",
    priority: "3", category: "", reminderMinutes: "",
};

function CreateForm({ onCreated, onCancel }: {
    onCreated: (todo: Todo) => void;
    onCancel: () => void;
}) {
    const [form, setForm] = useState<CreateFormState>(EMPTY_FORM);
    const [error, setError] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);

    function set(field: keyof CreateFormState) {
        return (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
            setForm(f => ({ ...f, [field]: e.target.value }));
        };
    }

    async function handleSubmit(e: React.FormEvent) {
        e.preventDefault();
        if (!form.title.trim()) { setError("Titel ist erforderlich."); return; }
        setLoading(true);
        setError(null);
        try {
            const res = await createTodo({
                title: form.title.trim(),
                description: form.description.trim() || undefined,
                dueDate: form.dueDate || undefined,
                dueTime: form.dueTime || undefined,
                priority: Number(form.priority) as TodoPriority,
                category: form.category || undefined,
                reminderMinutes: form.reminderMinutes ? Number(form.reminderMinutes) : undefined,
                source: "dashboard",
            });
            onCreated(res.todo);
        } catch (err) {
            setError(err instanceof Error ? err.message : String(err));
        } finally {
            setLoading(false);
        }
    }

    return (
        <form className="todo-create-form" onSubmit={handleSubmit}>
            {error && <div className="error-box">{error}</div>}

            <div className="form-row">
                <label className="form-label">Titel *</label>
                <input
                    className="form-input"
                    value={form.title}
                    onChange={set("title")}
                    placeholder="Was muss erledigt werden?"
                    autoFocus
                    maxLength={500}
                />
            </div>

            <div className="form-row">
                <label className="form-label">Beschreibung</label>
                <textarea
                    className="form-input"
                    value={form.description}
                    onChange={set("description")}
                    placeholder="Details, Notizen …"
                    rows={2}
                    maxLength={2000}
                />
            </div>

            <div className="form-row-2col">
                <div className="form-row">
                    <label className="form-label">Fälligkeitsdatum</label>
                    <input className="form-input" type="date" value={form.dueDate} onChange={set("dueDate")} min={today()} />
                </div>
                <div className="form-row">
                    <label className="form-label">Uhrzeit</label>
                    <input className="form-input" type="time" value={form.dueTime} onChange={set("dueTime")} />
                </div>
            </div>

            <div className="form-row-2col">
                <div className="form-row">
                    <label className="form-label">Priorität</label>
                    <select className="form-input" value={form.priority} onChange={set("priority")}>
                        <option value="1">1 – Kritisch</option>
                        <option value="2">2 – Hoch</option>
                        <option value="3">3 – Mittel</option>
                        <option value="4">4 – Niedrig</option>
                        <option value="5">5 – Optional</option>
                    </select>
                </div>
                <div className="form-row">
                    <label className="form-label">Kategorie</label>
                    <select className="form-input" value={form.category} onChange={set("category")}>
                        <option value="">— keine —</option>
                        {CATEGORY_OPTIONS.map(c => (
                            <option key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</option>
                        ))}
                    </select>
                </div>
            </div>

            <div className="form-row">
                <label className="form-label">Erinnerung (Minuten vorher)</label>
                <input
                    className="form-input"
                    type="number"
                    min={0}
                    max={10080}
                    value={form.reminderMinutes}
                    onChange={set("reminderMinutes")}
                    placeholder="z.B. 60 = 1h vorher"
                />
            </div>

            <div className="form-actions">
                <button type="submit" disabled={loading}>
                    {loading ? "Wird erstellt …" : "Todo erstellen"}
                </button>
                <button type="button" className="secondary" onClick={onCancel}>Abbrechen</button>
            </div>
        </form>
    );
}

// ── Detail-Modal ───────────────────────────────────────────────────────────

function TodoDetailModal({ todo, onClose, onUpdated }: {
    todo: Todo;
    onClose: () => void;
    onUpdated: (t: Todo) => void;
}) {
    const [editing, setEditing] = useState(false);
    const [dueDate, setDueDate] = useState(todo.dueDate ?? "");
    const [dueTime, setDueTime] = useState(todo.dueTime ?? "");
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);

    async function handleReschedule() {
        if (!dueDate) return;
        setSaving(true);
        setError(null);
        try {
            const res = await updateTodo(todo.id, {
                dueDate: dueDate || undefined,
                dueTime: dueTime || undefined,
            });
            onUpdated(res.todo);
            setEditing(false);
        } catch (e) {
            setError(e instanceof Error ? e.message : String(e));
        } finally {
            setSaving(false);
        }
    }

    return (
        <Modal title={todo.title} onClose={onClose}>
            {error && <div className="error-box">{error}</div>}

            <div className="kv-list" style={{ marginBottom: 16 }}>
                {[
                    ["Status", <StatusBadge key="s" status={todo.status} />],
                    ["Priorität", <span key="p" className={`badge ${PRIORITY_COLORS[todo.priority as TodoPriority] ?? "info"}`}>{PRIORITY_LABELS[todo.priority as TodoPriority]}</span>],
                    ["Kategorie", todo.category ?? "—"],
                    ["Fällig", todo.dueDate ? `${fmtDate(todo.dueDate)}${todo.dueTime ? ` · ${todo.dueTime}` : ""}` : "—"],
                    ["Erinnerung", todo.reminderMinutes != null ? `${todo.reminderMinutes} Min vorher` : "—"],
                    ["Quelle", todo.source],
                    ["Erstellt", new Date(todo.createdAt).toLocaleString("de-DE")],
                    ["Erledigt", todo.completedAt ? new Date(todo.completedAt).toLocaleString("de-DE") : "—"],
                ].map(([label, value]) => (
                    <div className="kv-item" key={String(label)}>
                        <span className="kv-label">{String(label)}</span>
                        <span className="kv-value">{value as React.ReactNode}</span>
                    </div>
                ))}
            </div>

            {todo.description && (
                <div className="todo-description">{todo.description}</div>
            )}

            {editing ? (
                <div className="form-row-2col" style={{ marginTop: 12 }}>
                    <div className="form-row">
                        <label className="form-label">Neues Datum</label>
                        <input className="form-input" type="date" value={dueDate}
                            onChange={e => setDueDate(e.target.value)} />
                    </div>
                    <div className="form-row">
                        <label className="form-label">Uhrzeit</label>
                        <input className="form-input" type="time" value={dueTime}
                            onChange={e => setDueTime(e.target.value)} />
                    </div>
                    <div className="form-actions" style={{ gridColumn: "1/-1" }}>
                        <button onClick={handleReschedule} disabled={saving || !dueDate}>
                            {saving ? "Wird gespeichert …" : "Datum speichern"}
                        </button>
                        <button className="secondary" onClick={() => setEditing(false)}>Abbrechen</button>
                    </div>
                </div>
            ) : (
                <div className="form-actions" style={{ marginTop: 12 }}>
                    {todo.status !== "done" && todo.status !== "cancelled" && (
                        <button className="secondary" onClick={() => setEditing(true)}>Datum ändern</button>
                    )}
                </div>
            )}

            {todo.history.length > 0 && (
                <details className="json-details" style={{ marginTop: 12 }}>
                    <summary>Verlauf ({todo.history.length})</summary>
                    <div className="table-wrap" style={{ marginTop: 8 }}>
                        <table>
                            <thead>
                                <tr>
                                    <th>Zeit</th><th>Aktion</th><th>Vorher</th><th>Nachher</th>
                                </tr>
                            </thead>
                            <tbody>
                                {[...todo.history].reverse().map((h, i) => (
                                    <tr key={i}>
                                        <td>{new Date(h.timestamp).toLocaleString("de-DE")}</td>
                                        <td>{h.action}</td>
                                        <td className="muted">{h.oldValue ?? "—"}</td>
                                        <td>{h.newValue ?? "—"}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </details>
            )}
        </Modal>
    );
}

// ── Haupt-Komponente ───────────────────────────────────────────────────────

export function TodoPage({ onAuthRequired }: Props) {
    const [todos, setTodos] = useState<Todo[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [showCreate, setShowCreate] = useState(false);
    const [detailTodo, setDetailTodo] = useState<Todo | null>(null);
    const [filterStatus, setFilterStatus] = useState<string>("open");
    const [filterCategory, setFilterCategory] = useState<string>("");
    const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

    const load = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await getTodos({
                status: filterStatus || undefined,
                category: filterCategory || undefined,
            });
            setTodos(res.todos);
        } catch (e) {
            const msg = e instanceof Error ? e.message : String(e);
            if (msg === "AUTH_REQUIRED") { onAuthRequired(); return; }
            setError(msg);
        } finally {
            setLoading(false);
        }
    }, [filterStatus, filterCategory, onAuthRequired]);

    useEffect(() => { void load(); }, [load]);

    async function handleComplete(id: string) {
        try {
            const res = await completeTodo(id);
            setTodos(prev => prev.map(t => t.id === id ? res.todo : t));
        } catch (e) {
            const msg = e instanceof Error ? e.message : String(e);
            if (msg === "AUTH_REQUIRED") onAuthRequired();
            else setError(msg);
        }
    }

    async function handleDelete(id: string) {
        try {
            await deleteTodo(id);
            setTodos(prev => prev.filter(t => t.id !== id));
            setConfirmDelete(null);
        } catch (e) {
            const msg = e instanceof Error ? e.message : String(e);
            if (msg === "AUTH_REQUIRED") onAuthRequired();
            else setError(msg);
        }
    }

    function handleCreated(todo: Todo) {
        setTodos(prev => [todo, ...prev]);
        setShowCreate(false);
    }

    function handleUpdated(updated: Todo) {
        setTodos(prev => prev.map(t => t.id === updated.id ? updated : t));
        setDetailTodo(updated);
    }

    const openCount = todos.filter(t => t.status === "open" || t.status === "in_progress").length;
    const overdueCount = todos.filter(isOverdue).length;

    return (
        <div className="dashboard-shell">
            {/* Header */}
            <div className="app-header">
                <div>
                    <h1>Todos</h1>
                    <span className="muted">
                        {loading ? "Lädt …" : `${todos.length} Einträge · ${openCount} offen${overdueCount > 0 ? ` · ${overdueCount} überfällig` : ""}`}
                    </span>
                </div>
                <div className="header-actions">
                    <button onClick={() => setShowCreate(true)}>+ Todo erstellen</button>
                    <button className="secondary" onClick={load} disabled={loading}>Aktualisieren</button>
                </div>
            </div>

            <div style={{ padding: "16px 0" }}>
                {error && <div className="error-box">{error}</div>}

                {/* Filter-Leiste */}
                <div className="todo-filter-bar">
                    <select
                        className="form-input"
                        value={filterStatus}
                        onChange={e => setFilterStatus(e.target.value)}
                    >
                        <option value="">Alle Status</option>
                        <option value="open">Offen</option>
                        <option value="in_progress">In Arbeit</option>
                        <option value="done">Erledigt</option>
                        <option value="cancelled">Abgebrochen</option>
                    </select>

                    <select
                        className="form-input"
                        value={filterCategory}
                        onChange={e => setFilterCategory(e.target.value)}
                    >
                        <option value="">Alle Kategorien</option>
                        {CATEGORY_OPTIONS.map(c => (
                            <option key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</option>
                        ))}
                    </select>
                </div>

                {/* Statistik-Kacheln */}
                <div className="metric-grid" style={{ marginBottom: 16 }}>
                    {([
                        ["Gesamt", todos.length, ""],
                        ["Offen", openCount, "ok"],
                        ["Überfällig", overdueCount, overdueCount > 0 ? "bad" : "ok"],
                        ["Erledigt", todos.filter(t => t.status === "done").length, "info"],
                    ] as const).map(([label, value, color]) => (
                        <div key={label} className="metric-card">
                            <span className="metric-label">{label}</span>
                            <div className={`metric-value ${color ? `text-${color}` : ""}`}>{value}</div>
                        </div>
                    ))}
                </div>

                {/* Todo-Liste */}
                <Panel title="Todos" action={
                    <span className="muted" style={{ fontSize: 13 }}>
                        {filterStatus ? STATUS_LABELS[filterStatus as TodoStatus] : "Alle"} · {todos.length} Einträge
                    </span>
                }>
                    {todos.length === 0 ? (
                        <div className="empty">Keine Todos gefunden.</div>
                    ) : (
                        <div className="todo-list">
                            {todos.map(todo => (
                                <div
                                    key={todo.id}
                                    className={`todo-row ${isOverdue(todo) ? "todo-overdue" : ""} ${todo.status === "done" ? "todo-done" : ""}`}
                                >
                                    {/* Linke Seite: Status-Check + Inhalt */}
                                    <div className="todo-row-main">
                                        {/* Checkbox / Complete */}
                                        {todo.status !== "done" && todo.status !== "cancelled" && (
                                            <button
                                                className="todo-check-btn"
                                                title="Als erledigt markieren"
                                                onClick={() => void handleComplete(todo.id)}
                                                aria-label="Erledigen"
                                            >
                                                ○
                                            </button>
                                        )}
                                        {(todo.status === "done" || todo.status === "cancelled") && (
                                            <span className="todo-check-done" aria-label="Erledigt">✓</span>
                                        )}

                                        <div className="todo-row-content" onClick={() => setDetailTodo(todo)}>
                                            <span className="todo-title">{todo.title}</span>
                                            <div className="todo-meta">
                                                {todo.dueDate && (
                                                    <span className={`todo-due ${isOverdue(todo) ? "text-bad" : "muted"}`}>
                                                        📅 {fmtDate(todo.dueDate)}{todo.dueTime ? ` · ${todo.dueTime}` : ""}
                                                    </span>
                                                )}
                                                {todo.category && (
                                                    <span className="todo-tag">{todo.category}</span>
                                                )}
                                                {todo.reminderMinutes != null && (
                                                    <span className="todo-tag muted">⏰ {todo.reminderMinutes}min</span>
                                                )}
                                            </div>
                                        </div>
                                    </div>

                                    {/* Rechte Seite: Priorität + Aktionen */}
                                    <div className="todo-row-actions">
                                        <span className={`badge ${PRIORITY_COLORS[todo.priority as TodoPriority] ?? "info"}`}>
                                            P{todo.priority}
                                        </span>
                                        <StatusBadge status={todo.status} />
                                        {confirmDelete === todo.id ? (
                                            <>
                                                <button className="btn-danger" onClick={() => void handleDelete(todo.id)}>
                                                    Löschen
                                                </button>
                                                <button className="secondary" onClick={() => setConfirmDelete(null)}>
                                                    Abbruch
                                                </button>
                                            </>
                                        ) : (
                                            <button
                                                className="secondary"
                                                style={{ padding: "4px 8px", fontSize: 12 }}
                                                onClick={e => { e.stopPropagation(); setConfirmDelete(todo.id); }}
                                                title="Löschen"
                                            >
                                                🗑
                                            </button>
                                        )}
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </Panel>
            </div>

            {/* Create Modal */}
            {showCreate && (
                <Modal title="Neues Todo" onClose={() => setShowCreate(false)}>
                    <CreateForm onCreated={handleCreated} onCancel={() => setShowCreate(false)} />
                </Modal>
            )}

            {/* Detail Modal */}
            {detailTodo && (
                <TodoDetailModal
                    todo={detailTodo}
                    onClose={() => setDetailTodo(null)}
                    onUpdated={handleUpdated}
                />
            )}
        </div>
    );
}
