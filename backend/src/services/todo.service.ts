import { getDb } from './db.js';
import { appendAuditEvent } from './audit-log.js';
import {
  createTodoId,
  type JarvisTodo,
  type RecurrenceRule,
  type TodoHistoryEntry,
  type TodoPriority,
  type TodoSource,
  type TodoStatus,
} from '../types/todo.types.js';

// ── Typen ─────────────────────────────────────────────────────────────────────

export type CreateTodoInput = {
  title: string;
  description?: string;
  status?: TodoStatus;
  priority?: TodoPriority;
  category?: string;
  dueDate?: string;
  dueTime?: string;
  startDate?: string;
  recurrence?: RecurrenceRule;
  reminderMinutes?: number;
  shiftId?: string;
  source?: TodoSource;
};

export type UpdateTodoInput = {
  title?: string;
  description?: string;
  status?: TodoStatus;
  priority?: TodoPriority;
  category?: string;
  dueDate?: string;
  dueTime?: string;
  reminderMinutes?: number;
  recurrence?: RecurrenceRule;
  shiftId?: string;
};

export type TodoFilter = {
  status?: TodoStatus;
  priority?: TodoPriority;
  category?: string;
  due_date?: string;
  limit?: number;
};

// ── DB-Row → JarvisTodo ───────────────────────────────────────────────────────

type TodoRow = {
  id: string;
  title: string;
  description: string;
  status: string;
  priority: number;
  category: string;
  due_date: string | null;
  due_time: string | null;
  start_date: string | null;
  recurrence: string;
  reminder_min: number | null;
  shift_id: string | null;
  source: string;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  history: string;
};

function rowToTodo(row: TodoRow): JarvisTodo {
  return {
    id: row.id,
    title: row.title,
    description: row.description || undefined,
    status: row.status as TodoStatus,
    priority: row.priority as TodoPriority,
    category: row.category || undefined,
    dueDate: row.due_date ?? undefined,
    dueTime: row.due_time ?? undefined,
    startDate: row.start_date ?? undefined,
    recurrence:
      row.recurrence && row.recurrence !== 'none'
        ? (JSON.parse(row.recurrence) as RecurrenceRule)
        : undefined,
    reminderMinutes: row.reminder_min ?? undefined,
    shiftId: row.shift_id ?? undefined,
    source: row.source as TodoSource,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
    completedAt: row.completed_at ?? undefined,
    history: JSON.parse(row.history || '[]') as TodoHistoryEntry[],
  };
}

// ── Lese-Operationen ──────────────────────────────────────────────────────────

export function getTodoById(id: string): JarvisTodo | null {
  const db = getDb();
  const row = db.prepare('SELECT * FROM todos WHERE id = ?').get(id) as TodoRow | undefined;
  return row ? rowToTodo(row) : null;
}

export function listTodos(filter: TodoFilter): JarvisTodo[] {
  const db = getDb();

  const conditions: string[] = [];
  const params: Record<string, unknown> = {};

  if (filter.status) {
    conditions.push('status = @status');
    params.status = filter.status;
  }
  if (filter.priority !== undefined) {
    conditions.push('priority = @priority');
    params.priority = filter.priority;
  }
  if (filter.category) {
    conditions.push('category = @category');
    params.category = filter.category;
  }
  if (filter.due_date) {
    conditions.push('due_date = @due_date');
    params.due_date = filter.due_date;
  }

  const where = conditions.length > 0 ? `WHERE ${conditions.join(' AND ')}` : '';
  params.limit = filter.limit ?? 100;

  const rows = db
    .prepare(
      `SELECT * FROM todos ${where}
       ORDER BY
         CASE WHEN due_date IS NULL THEN 1 ELSE 0 END,
         due_date ASC,
         priority ASC,
         created_at ASC
       LIMIT @limit`,
    )
    .all(params) as TodoRow[];

  return rows.map(rowToTodo);
}

// due_date <= heute UND status nicht done/cancelled
export function getTodosToday(): JarvisTodo[] {
  const db = getDb();
  const today = new Date().toISOString().slice(0, 10);

  const rows = db
    .prepare(
      `SELECT * FROM todos
       WHERE status NOT IN ('done', 'cancelled')
         AND (due_date IS NULL OR due_date <= @today)
       ORDER BY
         CASE WHEN due_date IS NULL THEN 1 ELSE 0 END,
         due_date ASC,
         priority ASC`,
    )
    .all({ today }) as TodoRow[];

  return rows.map(rowToTodo);
}

// ── Schreib-Operationen ───────────────────────────────────────────────────────

export function createTodo(data: CreateTodoInput): JarvisTodo {
  const db = getDb();
  const now = new Date().toISOString();
  const id = createTodoId();
  const source: TodoSource = data.source ?? 'manual';

  const history: TodoHistoryEntry[] = [
    { timestamp: now, action: 'created', actor: source, newValue: data.title },
  ];

  db.prepare(
    `INSERT INTO todos (
       id, title, description, status, priority, category,
       due_date, due_time, start_date, recurrence, reminder_min,
       shift_id, source, created_at, updated_at, completed_at, history
     ) VALUES (
       @id, @title, @description, @status, @priority, @category,
       @due_date, @due_time, @start_date, @recurrence, @reminder_min,
       @shift_id, @source, @created_at, @updated_at, NULL, @history
     )`,
  ).run({
    id,
    title: data.title,
    description: data.description ?? '',
    status: data.status ?? 'open',
    priority: data.priority ?? 3,
    category: data.category ?? '',
    due_date: data.dueDate ?? null,
    due_time: data.dueTime ?? null,
    start_date: data.startDate ?? null,
    recurrence: data.recurrence ? JSON.stringify(data.recurrence) : 'none',
    reminder_min: data.reminderMinutes ?? null,
    shift_id: data.shiftId ?? null,
    source,
    created_at: now,
    updated_at: now,
    history: JSON.stringify(history),
  });

  appendAuditEvent({
    component: 'todo.service',
    action: 'todo.create',
    result: 'completed',
    message: `Todo erstellt: ${data.title}`,
    details: { id, title: data.title, source },
  });

  return getTodoById(id)!;
}

export function updateTodo(
  id: string,
  data: Partial<UpdateTodoInput>,
  actor: TodoSource = 'manual',
): JarvisTodo | null {
  const existing = getTodoById(id);
  if (!existing) return null;

  const db = getDb();
  const now = new Date().toISOString();
  const newHistory: TodoHistoryEntry[] = [...existing.history];

  // History-Eintrag nur bei tatsächlicher Änderung
  const track = (
    action: TodoHistoryEntry['action'],
    oldVal: string | undefined,
    newVal: string | undefined,
  ) => {
    if (String(oldVal ?? '') !== String(newVal ?? '')) {
      newHistory.push({ timestamp: now, action, actor, oldValue: oldVal ?? '', newValue: newVal ?? '' });
    }
  };

  if (data.title !== undefined) track('updated', existing.title, data.title);
  if (data.status !== undefined) {
    const action: TodoHistoryEntry['action'] =
      data.status === 'done'
        ? 'completed'
        : data.status === 'cancelled'
          ? 'cancelled'
          : 'updated';
    track(action, existing.status, data.status);
  }
  if (data.priority !== undefined) track('priority_changed', String(existing.priority), String(data.priority));
  if (data.dueDate !== undefined) track('rescheduled', existing.dueDate, data.dueDate);
  if (data.reminderMinutes !== undefined) track('reminder_set', String(existing.reminderMinutes ?? ''), String(data.reminderMinutes));

  const completedAt =
    data.status === 'done' ? (existing.completedAt ?? now) : existing.completedAt;

  const newRecurrence =
    data.recurrence !== undefined
      ? JSON.stringify(data.recurrence)
      : existing.recurrence
        ? JSON.stringify(existing.recurrence)
        : 'none';

  db.prepare(
    `UPDATE todos SET
       title        = @title,
       description  = @description,
       status       = @status,
       priority     = @priority,
       category     = @category,
       due_date     = @due_date,
       due_time     = @due_time,
       reminder_min = @reminder_min,
       recurrence   = @recurrence,
       shift_id     = @shift_id,
       updated_at   = @updated_at,
       completed_at = @completed_at,
       history      = @history
     WHERE id = @id`,
  ).run({
    id,
    title: data.title ?? existing.title,
    description: data.description !== undefined ? data.description : (existing.description ?? ''),
    status: data.status ?? existing.status,
    priority: data.priority ?? existing.priority,
    category: data.category !== undefined ? data.category : (existing.category ?? ''),
    due_date: data.dueDate !== undefined ? (data.dueDate ?? null) : (existing.dueDate ?? null),
    due_time: data.dueTime !== undefined ? (data.dueTime ?? null) : (existing.dueTime ?? null),
    reminder_min: data.reminderMinutes !== undefined ? (data.reminderMinutes ?? null) : (existing.reminderMinutes ?? null),
    recurrence: newRecurrence,
    shift_id: data.shiftId !== undefined ? (data.shiftId ?? null) : (existing.shiftId ?? null),
    updated_at: now,
    completed_at: completedAt ?? null,
    history: JSON.stringify(newHistory),
  });

  appendAuditEvent({
    component: 'todo.service',
    action: 'todo.update',
    result: 'completed',
    message: `Todo aktualisiert: ${existing.title}`,
    details: { id, changes: data, actor },
  });

  return getTodoById(id)!;
}

// Soft-delete: Status auf 'cancelled' setzen
export function deleteTodo(id: string): void {
  updateTodo(id, { status: 'cancelled' }, 'manual');
}

export function completeTodo(id: string, actor: TodoSource = 'manual'): JarvisTodo | null {
  return updateTodo(id, { status: 'done' }, actor);
}
