export type TodoStatus = "open" | "in_progress" | "done" | "cancelled";
export type TodoPriority = 1 | 2 | 3 | 4 | 5;
export type TodoSource = "voice" | "dashboard" | "discord" | "manual" | "routine";

export type RecurrenceRule = {
    type: "daily" | "weekly" | "monthly";
    interval: number;
    daysOfWeek?: number[];
};

export type TodoHistoryEntry = {
    timestamp: string;
    action: string;
    actor: string;
    oldValue?: string;
    newValue?: string;
};

export type Todo = {
    id: string;
    title: string;
    description?: string;
    status: TodoStatus;
    priority: TodoPriority;
    category?: string;
    dueDate?: string;   // YYYY-MM-DD
    dueTime?: string;   // HH:MM
    startDate?: string;
    recurrence?: RecurrenceRule;
    reminderMinutes?: number;
    shiftId?: string;
    source: TodoSource;
    createdAt: string;
    updatedAt: string;
    completedAt?: string;
    history: TodoHistoryEntry[];
};

export type TodoListResponse = {
    ok: boolean;
    count: number;
    todos: Todo[];
};

export type TodoResponse = {
    ok: boolean;
    todo: Todo;
};

export const PRIORITY_LABELS: Record<TodoPriority, string> = {
    1: "Kritisch",
    2: "Hoch",
    3: "Mittel",
    4: "Niedrig",
    5: "Optional",
};

export const PRIORITY_COLORS: Record<TodoPriority, string> = {
    1: "bad",
    2: "warn",
    3: "info",
    4: "ok",
    5: "muted",
};

export const STATUS_LABELS: Record<TodoStatus, string> = {
    open: "Offen",
    in_progress: "In Arbeit",
    done: "Erledigt",
    cancelled: "Abgebrochen",
};

export const CATEGORY_OPTIONS = [
    "arbeit", "privat", "streaming", "haushalt", "gesundheit", "finanzen",
] as const;
