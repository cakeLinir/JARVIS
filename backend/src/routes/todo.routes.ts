import type { FastifyInstance } from "fastify";
import { z } from "zod";
import { requireAnyJarvisAuth } from "../security/auth.js";
import {
    completeTodo,
    createTodo,
    deleteTodo,
    getAllTodos,
    getDueTodayTodos,
    getTodoById,
    rescheduleTodo,
    updateTodo,
} from "../services/todo-store.js";
import type { TodoPriority, TodoSource, TodoStatus } from "../types/todo.types.js";

// ── Validation Schemas ────────────────────────────────────────────────────

const PrioritySchema = z.union([z.literal(1), z.literal(2), z.literal(3), z.literal(4), z.literal(5)]);
const StatusSchema = z.enum(["open", "in_progress", "done", "cancelled"]);
const SourceSchema = z.enum(["voice", "dashboard", "discord", "manual", "routine"]);

const RecurrenceSchema = z.object({
    type: z.enum(["daily", "weekly", "monthly"]),
    interval: z.number().int().min(1).max(365),
    daysOfWeek: z.array(z.number().int().min(0).max(6)).optional(),
}).optional();

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
    reminderMinutes: z.number().int().min(0).max(10080).optional(), // max 1 Woche
    shiftId: z.string().optional(),
    source: SourceSchema.optional(),
});

const UpdateTodoSchema = z.object({
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
}).refine(d => Object.keys(d).length > 0, { message: "Mindestens ein Feld erforderlich." });

const RescheduleSchema = z.object({
    dueDate: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, "Format: YYYY-MM-DD"),
    dueTime: z.string().regex(/^\d{2}:\d{2}$/).optional(),
    actor: SourceSchema.optional(),
});

const QuerySchema = z.object({
    status: StatusSchema.optional(),
    category: z.string().optional(),
    date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/).optional(),
    limit: z.string().optional().transform(v => v ? Math.min(200, parseInt(v, 10)) : 100),
});

// ── Routes ─────────────────────────────────────────────────────────────────

export async function todoRoutes(server: FastifyInstance) {

    // GET /api/todos — Liste aller Todos (optional gefiltert)
    server.get("/api/todos", { preHandler: requireAnyJarvisAuth }, async (req, reply) => {
        const q = QuerySchema.safeParse(req.query);
        if (!q.success) return reply.code(400).send({ error: "invalid_query", details: q.error.flatten() });

        let result = getAllTodos();

        if (q.data.status) result = result.filter(t => t.status === q.data.status);
        if (q.data.category) result = result.filter(t => t.category === q.data.category);
        if (q.data.date) result = result.filter(t => t.dueDate === q.data.date);

        // Sortierung: Fälligkeit aufsteigend, dann Priorität aufsteigend
        result.sort((a, b) => {
            const dateDiff = (a.dueDate ?? "9999").localeCompare(b.dueDate ?? "9999");
            if (dateDiff !== 0) return dateDiff;
            return (a.priority ?? 3) - (b.priority ?? 3);
        });

        return { ok: true, count: result.length, todos: result.slice(0, q.data.limit) };
    });

    // GET /api/todos/due-today — Heute fällig oder überfällig
    server.get("/api/todos/due-today", { preHandler: requireAnyJarvisAuth }, async () => {
        const todos = getDueTodayTodos();
        return { ok: true, count: todos.length, todos };
    });

    // GET /api/todos/:id
    server.get("/api/todos/:id", { preHandler: requireAnyJarvisAuth }, async (req, reply) => {
        const { id } = req.params as { id: string };
        const todo = getTodoById(id);
        if (!todo) return reply.code(404).send({ error: "todo_not_found" });
        return { ok: true, todo };
    });

    // POST /api/todos — Neues Todo erstellen
    server.post("/api/todos", { preHandler: requireAnyJarvisAuth }, async (req, reply) => {
        const parsed = CreateTodoSchema.safeParse(req.body);
        if (!parsed.success) return reply.code(400).send({ error: "invalid_todo_payload", details: parsed.error.flatten() });

        const todo = createTodo({
            title: parsed.data.title,
            description: parsed.data.description,
            status: (parsed.data.status ?? "open") as TodoStatus,
            priority: (parsed.data.priority ?? 2) as TodoPriority,
            category: parsed.data.category,
            dueDate: parsed.data.dueDate,
            dueTime: parsed.data.dueTime,
            startDate: parsed.data.startDate,
            recurrence: parsed.data.recurrence,
            reminderMinutes: parsed.data.reminderMinutes,
            shiftId: parsed.data.shiftId,
            source: (parsed.data.source ?? "manual") as TodoSource,
        });

        return reply.code(201).send({ ok: true, todo });
    });

    // PATCH /api/todos/:id — Felder aktualisieren
    server.patch("/api/todos/:id", { preHandler: requireAnyJarvisAuth }, async (req, reply) => {
        const { id } = req.params as { id: string };
        const parsed = UpdateTodoSchema.safeParse(req.body);
        if (!parsed.success) return reply.code(400).send({ error: "invalid_update_payload", details: parsed.error.flatten() });

        const actor = ((req.body as Record<string, unknown>)?.actor ?? "manual") as TodoSource;
        const todo = updateTodo(id, parsed.data, actor);
        if (!todo) return reply.code(404).send({ error: "todo_not_found" });
        return { ok: true, todo };
    });

    // POST /api/todos/:id/complete — Als erledigt markieren
    server.post("/api/todos/:id/complete", { preHandler: requireAnyJarvisAuth }, async (req, reply) => {
        const { id } = req.params as { id: string };
        const actor = ((req.body as Record<string, unknown>)?.actor ?? "manual") as TodoSource;
        const todo = completeTodo(id, actor);
        if (!todo) return reply.code(404).send({ error: "todo_not_found" });
        return { ok: true, todo };
    });

    // POST /api/todos/:id/reschedule — Verschieben
    server.post("/api/todos/:id/reschedule", { preHandler: requireAnyJarvisAuth }, async (req, reply) => {
        const { id } = req.params as { id: string };
        const parsed = RescheduleSchema.safeParse(req.body);
        if (!parsed.success) return reply.code(400).send({ error: "invalid_reschedule_payload", details: parsed.error.flatten() });

        const actor = (parsed.data.actor ?? "manual") as TodoSource;
        const todo = rescheduleTodo(id, parsed.data.dueDate, parsed.data.dueTime, actor);
        if (!todo) return reply.code(404).send({ error: "todo_not_found" });
        return { ok: true, todo };
    });

    // DELETE /api/todos/:id
    server.delete("/api/todos/:id", { preHandler: requireAnyJarvisAuth }, async (req, reply) => {
        const { id } = req.params as { id: string };
        const ok = deleteTodo(id);
        if (!ok) return reply.code(404).send({ error: "todo_not_found" });
        return { ok: true };
    });
}
