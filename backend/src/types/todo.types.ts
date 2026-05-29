import { randomUUID } from "node:crypto";

export type TodoStatus = "open" | "in_progress" | "done" | "cancelled";
export type TodoPriority = 1 | 2 | 3 | 4 | 5;
export type TodoSource = "voice" | "dashboard" | "discord" | "manual" | "routine";
export type RecurrenceType = "daily" | "weekly" | "monthly";

export type RecurrenceRule = {
    type: RecurrenceType;
    interval: number;        // z.B. 1 = jede Woche, 2 = alle 2 Wochen
    daysOfWeek?: number[];   // 0=Mo … 6=So (nur bei weekly)
};

export type TodoHistoryAction =
    | "created"
    | "updated"
    | "completed"
    | "rescheduled"
    | "priority_changed"
    | "reminder_set"
    | "cancelled";

export type TodoHistoryEntry = {
    timestamp: string;
    action: TodoHistoryAction;
    actor: TodoSource;
    oldValue?: string;
    newValue?: string;
};

export type JarvisTodo = {
    id: string;
    title: string;
    description?: string;
    status: TodoStatus;
    priority: TodoPriority;
    category?: string;
    dueDate?: string;           // YYYY-MM-DD
    dueTime?: string;           // HH:MM
    startDate?: string;         // YYYY-MM-DD
    recurrence?: RecurrenceRule;
    reminderMinutes?: number;   // Minuten vor Fälligkeit → Agent feuert Reminder
    shiftId?: string;           // optionale Schicht-Verknüpfung
    source: TodoSource;
    createdAt: string;
    updatedAt: string;
    completedAt?: string;
    history: TodoHistoryEntry[];
};

export function createTodoId(): string {
    return `todo_${Date.now()}_${randomUUID().slice(0, 8)}`;
}
