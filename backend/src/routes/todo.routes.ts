import type { FastifyInstance } from 'fastify';
import { z } from 'zod';
import { requireAnyJarvisAuth } from '../security/auth.js';
import {
  completeTodo,
  createTodo,
  deleteTodo,
  getTodoById,
  getTodosToday,
  listTodos,
  updateTodo,
} from '../services/todo.service.js';
import type { JarvisTodo, RecurrenceRule, TodoSource, TodoStatus } from '../types/todo.types.js';

// ── Validation Schemas ────────────────────────────────────────────────────────

const PrioritySchema = z.union([
  z.literal(1), z.literal(2), z.literal(3), z.literal(4), z.literal(5),
]);

const StatusSchema = z.enum(['open', 'in_progress', 'done', 'cancelled']);

const SourceSchema = z.enum(['voice', 'dashboard', 'discord', 'manual', 'routine']);

const RecurrenceSchema = z
  .object({
    type: z.enum(['daily', 'weekly', 'monthly']),
    interval: z.number().int().min(1).max(365),
    daysOfWeek: z.array(z.number().int().min(0).max(6)).optional(),
  })
  .optional();

const CreateTodoSchema = z.object({
  title: z.string().min(1).max(500).trim(),
  description: z.string().max(2000).optional(),
  status: StatusSchema.optional(),
  priority: PrioritySchema.optional(),
  category: z.string().max(100).optional(),
  dueDate: z.string().regex(/^\d{4}-\d{2}-\d{2}$/).optional(),
  dueTime: z.string().regex(/^\d{2}:\d{2}$/).optional(),
  startDate: z.string().regex(/^\d{4}-\d{2}-\d{2}$/).optional(),
  recurrence: RecurrenceSchema,
  reminderMinutes: z.number().int().min(0).max(10080).optional(),
  shiftId: z.string().optional(),
  source: SourceSchema.optional(),
});

const UpdateTodoSchema = z
  .object({
    title: z.string().min(1).max(500).trim().optional(),
    description: z.string().max(2000).optional(),
    status: StatusSchema.optional(),
    priority: PrioritySchema.optional(),
    category: z.string().max(100).optional(),
    dueDate: z.string().regex(/^\d{4}-\d{2}-\d{2}$/).optional(),
    dueTime: z.string().regex(/^\d{2}:\d{2}$/).optional(),
    reminderMinutes: z.number().int().min(0).max(10080).optional(),
    recurrence: RecurrenceSchema,
    shiftId: z.string().optional(),
  })
  .refine((d) => Object.keys(d).length > 0, { message: 'Mindestens ein Feld erforderlich.' });

const QuerySchema = z.object({
  status: StatusSchema.optional(),
  category: z.string().optional(),
  date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/).optional(),
  limit: z
    .string()
    .optional()
    .transform((v) => (v ? Math.min(200, parseInt(v, 10)) : 100)),
});

// ── Hilfsfunktionen ───────────────────────────────────────────────────────────

function todayStr(): string {
  return new Date().toISOString().slice(0, 10);
}

/** Berechnet das nächste Fälligkeitsdatum für eine Wiederholung. */
function nextRecurrenceDate(dueDate: string, recurrence: RecurrenceRule): string | null {
  try {
    const d = new Date(`${dueDate}T00:00:00`);
    switch (recurrence.type) {
      case 'daily':
        d.setDate(d.getDate() + recurrence.interval);
        break;
      case 'weekly':
        d.setDate(d.getDate() + 7 * recurrence.interval);
        break;
      case 'monthly':
        d.setMonth(d.getMonth() + recurrence.interval);
        break;
    }
    return d.toISOString().slice(0, 10);
  } catch {
    return null;
  }
}

/** Legt nach Abschluss eines wiederkehrenden TODOs die nächste Instanz an. */
function createNextRecurrence(completed: JarvisTodo): JarvisTodo | null {
  if (!completed.recurrence || !completed.dueDate) return null;
  const nextDate = nextRecurrenceDate(completed.dueDate, completed.recurrence);
  if (!nextDate) return null;

  return createTodo({
    title: completed.title,
    description: completed.description,
    priority: completed.priority,
    category: completed.category,
    dueDate: nextDate,
    dueTime: completed.dueTime,
    recurrence: completed.recurrence,
    reminderMinutes: completed.reminderMinutes,
    source: completed.source,
    status: 'open',
  });
}

// ── Routes ────────────────────────────────────────────────────────────────────

export async function todoRoutes(server: FastifyInstance) {

  // GET /api/todos — Liste aller Todos (optional gefiltert)
  server.get('/api/todos', { preHandler: requireAnyJarvisAuth }, async (req, reply) => {
    const q = QuerySchema.safeParse(req.query);
    if (!q.success)
      return reply.code(400).send({ error: 'invalid_query', details: q.error.flatten() });

    const todos = listTodos({
      status: q.data.status,
      category: q.data.category,
      due_date: q.data.date,
      limit: q.data.limit,
    });

    return { ok: true, count: todos.length, todos };
  });

  // GET /api/todos/today — Heute fällig oder überfällig (status != done/cancelled)
  server.get('/api/todos/today', { preHandler: requireAnyJarvisAuth }, async () => {
    const todos = getTodosToday();
    return { ok: true, count: todos.length, todos };
  });

  // GET /api/todos/:id
  server.get('/api/todos/:id', { preHandler: requireAnyJarvisAuth }, async (req, reply) => {
    const { id } = req.params as { id: string };
    const todo = getTodoById(id);
    if (!todo) return reply.code(404).send({ error: 'todo_not_found', message: `TODO '${id}' nicht gefunden.` });
    return { ok: true, todo };
  });

  // POST /api/todos — Neues Todo erstellen
  server.post('/api/todos', { preHandler: requireAnyJarvisAuth }, async (req, reply) => {
    const parsed = CreateTodoSchema.safeParse(req.body);
    if (!parsed.success)
      return reply.code(400).send({ error: 'invalid_todo_payload', details: parsed.error.flatten() });

    const todo = createTodo({
      title: parsed.data.title,
      description: parsed.data.description,
      status: (parsed.data.status ?? 'open') as TodoStatus,
      priority: parsed.data.priority,
      category: parsed.data.category,
      dueDate: parsed.data.dueDate,
      dueTime: parsed.data.dueTime,
      startDate: parsed.data.startDate,
      recurrence: parsed.data.recurrence,
      reminderMinutes: parsed.data.reminderMinutes,
      shiftId: parsed.data.shiftId,
      source: (parsed.data.source ?? 'manual') as TodoSource,
    });

    // Edge Case: Fälligkeitsdatum in der Vergangenheit → Warnung, kein Fehler
    const warnings: string[] = [];
    if (parsed.data.dueDate && parsed.data.dueDate < todayStr()) {
      warnings.push('Fälligkeitsdatum liegt in der Vergangenheit.');
    }

    return reply.code(201).send({ ok: true, todo, ...(warnings.length ? { warnings } : {}) });
  });

  // PATCH /api/todos/:id — Felder aktualisieren
  server.patch('/api/todos/:id', { preHandler: requireAnyJarvisAuth }, async (req, reply) => {
    const { id } = req.params as { id: string };

    const existing = getTodoById(id);
    if (!existing)
      return reply.code(404).send({ error: 'todo_not_found', message: `TODO '${id}' nicht gefunden.` });

    const parsed = UpdateTodoSchema.safeParse(req.body);
    if (!parsed.success)
      return reply.code(400).send({ error: 'invalid_update_payload', details: parsed.error.flatten() });

    const actor = ((req.body as Record<string, unknown>)?.actor ?? 'manual') as TodoSource;
    const todo = updateTodo(id, parsed.data, actor);

    // Edge Case: vergangenheits-Datum beim Update → Warnung
    const warnings: string[] = [];
    if (parsed.data.dueDate && parsed.data.dueDate < todayStr()) {
      warnings.push('Neues Fälligkeitsdatum liegt in der Vergangenheit.');
    }

    return { ok: true, todo, ...(warnings.length ? { warnings } : {}) };
  });

  // DELETE /api/todos/:id — Soft-delete (status = cancelled)
  server.delete('/api/todos/:id', { preHandler: requireAnyJarvisAuth }, async (req, reply) => {
    const { id } = req.params as { id: string };
    if (!getTodoById(id))
      return reply.code(404).send({ error: 'todo_not_found', message: `TODO '${id}' nicht gefunden.` });
    deleteTodo(id);
    return { ok: true };
  });

  // POST /api/todos/:id/complete — Als erledigt markieren
  // Edge Case: bei Wiederholung nächste Instanz anlegen
  server.post('/api/todos/:id/complete', { preHandler: requireAnyJarvisAuth }, async (req, reply) => {
    const { id } = req.params as { id: string };
    const existing = getTodoById(id);
    if (!existing)
      return reply.code(404).send({ error: 'todo_not_found', message: `TODO '${id}' nicht gefunden.` });

    const actor = ((req.body as Record<string, unknown>)?.actor ?? 'manual') as TodoSource;
    const todo = completeTodo(id, actor);

    // Nächste Wiederholung anlegen wenn Recurrence konfiguriert
    let nextTodo: JarvisTodo | null = null;
    if (existing.recurrence && existing.dueDate) {
      nextTodo = createNextRecurrence(existing);
    }

    return { ok: true, todo, ...(nextTodo ? { nextRecurrence: nextTodo } : {}) };
  });
}
