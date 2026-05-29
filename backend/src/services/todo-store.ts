import fs from "node:fs";
import path from "node:path";
import { appendAuditEvent } from "./audit-log.js";
import {
    createTodoId,
    type JarvisTodo,
    type TodoHistoryEntry,
    type TodoSource,
    type TodoStatus,
} from "../types/todo.types.js";

const dataDir = path.resolve(process.cwd(), ".runtime", "data");
const storePath = path.join(dataDir, "todos.json");

let todos: JarvisTodo[] = [];

// ── Persistenz ────────────────────────────────────────────────────────────────

function ensureStoreExists(): void {
    if (!fs.existsSync(dataDir)) fs.mkdirSync(dataDir, { recursive: true });
    if (!fs.existsSync(storePath)) {
        fs.writeFileSync(storePath, JSON.stringify({ version: 1, todos: [] }, null, 2), "utf-8");
    }
}

export function saveTodos(): void {
    ensureStoreExists();
    const tmp = `${storePath}.tmp`;
    fs.writeFileSync(tmp, JSON.stringify({ version: 1, todos }, null, 2), "utf-8");
    fs.renameSync(tmp, storePath);
}

export function loadTodos(): void {
    ensureStoreExists();
    try {
        const raw = fs.readFileSync(storePath, "utf-8");
        const parsed = JSON.parse(raw);
        todos = Array.isArray(parsed) ? parsed : (parsed?.todos ?? []);
    } catch {
        const backup = `${storePath}.broken-${Date.now()}.bak`;
        if (fs.existsSync(storePath)) fs.copyFileSync(storePath, backup);
        todos = [];
        saveTodos();
    }
}

// ── Read ──────────────────────────────────────────────────────────────────────

export function getAllTodos(): JarvisTodo[] {
    return [...todos];
}

export function getTodoById(id: string): JarvisTodo | null {
    return todos.find(t => t.id === id) ?? null;
}

export function getOpenTodos(): JarvisTodo[] {
    return todos.filter(t => t.status === "open" || t.status === "in_progress");
}

export function getDueTodayTodos(): JarvisTodo[] {
    const today = new Date().toISOString().slice(0, 10);
    return getOpenTodos().filter(t => !t.dueDate || t.dueDate <= today);
}

export function getTodosForDate(date: string): JarvisTodo[] {
    return getOpenTodos().filter(t => t.dueDate === date);
}

export function getDueForReminderTodos(): JarvisTodo[] {
    const now = Date.now();
    const results: JarvisTodo[] = [];

    for (const todo of getOpenTodos()) {
        if (!todo.dueDate || todo.reminderMinutes == null) continue;
        const dueStr = todo.dueTime ? `${todo.dueDate}T${todo.dueTime}:00` : `${todo.dueDate}T09:00:00`;
        const dueMs = new Date(dueStr).getTime();
        const fireMs = dueMs - todo.reminderMinutes * 60 * 1000;

        // Innerhalb des nächsten Polling-Fensters von 90 Sekunden fällig?
        if (fireMs <= now + 90_000 && fireMs >= now - 90_000) {
            results.push(todo);
        }
    }
    return results;
}

// ── Write ─────────────────────────────────────────────────────────────────────

export function createTodo(
    input: Omit<JarvisTodo, "id" | "createdAt" | "updatedAt" | "history"> & { status?: TodoStatus }
): JarvisTodo {
    const now = new Date().toISOString();
    const todo: JarvisTodo = {
        ...input,
        id: createTodoId(),
        status: input.status ?? "open",
        priority: input.priority ?? 3,
        source: input.source ?? "manual",
        createdAt: now,
        updatedAt: now,
        history: [{
            timestamp: now,
            action: "created",
            actor: input.source ?? "manual",
            newValue: input.title
        }]
    };
    todos.push(todo);
    saveTodos();
    appendAuditEvent({
        component: "todo-store", action: "todo.create", result: "completed",
        message: `Todo erstellt: ${todo.title}`,
        details: { id: todo.id, title: todo.title, source: todo.source }
    });
    return todo;
}

type TodoUpdateInput = Partial<Pick<
    JarvisTodo,
    "title" | "description" | "status" | "priority" | "category" |
    "dueDate" | "dueTime" | "reminderMinutes" | "recurrence" | "shiftId" | "notes"
>>;

export function updateTodo(
    id: string,
    changes: TodoUpdateInput,
    actor: TodoSource = "manual"
): JarvisTodo | null {
    const todo = todos.find(t => t.id === id);
    if (!todo) return null;

    const now = new Date().toISOString();
    const newEntries: TodoHistoryEntry[] = [];

    for (const [rawKey, newVal] of Object.entries(changes)) {
        const key = rawKey as keyof TodoUpdateInput;
        const oldVal = todo[key as keyof JarvisTodo];
        if (String(oldVal) === String(newVal)) continue;

        const action: TodoHistoryEntry["action"] =
            key === "status" ? (newVal === "done" ? "completed" : newVal === "cancelled" ? "cancelled" : "updated")
                : key === "dueDate" ? "rescheduled"
                    : key === "priority" ? "priority_changed"
                        : key === "reminderMinutes" ? "reminder_set"
                            : "updated";

        newEntries.push({ timestamp: now, action, actor, oldValue: String(oldVal ?? ""), newValue: String(newVal ?? "") });
        (todo as Record<string, unknown>)[key] = newVal;
    }

    if (changes.status === "done" && !todo.completedAt) todo.completedAt = now;
    todo.updatedAt = now;
    todo.history = [...todo.history, ...newEntries];
    saveTodos();

    appendAuditEvent({
        component: "todo-store", action: "todo.update", result: "completed",
        message: `Todo aktualisiert: ${todo.title}`,
        details: { id, changes }
    });
    return todo;
}

export function completeTodo(id: string, actor: TodoSource = "manual"): JarvisTodo | null {
    return updateTodo(id, { status: "done" }, actor);
}

export function rescheduleTodo(
    id: string, newDueDate: string, newDueTime?: string, actor: TodoSource = "manual"
): JarvisTodo | null {
    const changes: TodoUpdateInput = { dueDate: newDueDate };
    if (newDueTime !== undefined) changes.dueTime = newDueTime;
    return updateTodo(id, changes, actor);
}

export function deleteTodo(id: string): boolean {
    const idx = todos.findIndex(t => t.id === id);
    if (idx < 0) return false;
    const [removed] = todos.splice(idx, 1);
    saveTodos();
    appendAuditEvent({
        component: "todo-store", action: "todo.delete", result: "completed",
        message: `Todo gelöscht: ${removed.title}`, details: { id: removed.id }
    });
    return true;
}

export function getTodoStorePath(): string {
    ensureStoreExists();
    return storePath;
}
