import type { FastifyInstance } from "fastify";
import { z } from "zod";
import { requireAnyJarvisAuth } from "../security/auth.js";
import {
    deleteShift,
    getShiftByDate,
    getShiftById,
    getShiftsInRange,
    getTodayDateStr,
    getTomorrowDateStr,
    upsertShift,
} from "../services/shift-store.js";
import type { ShiftSource, ShiftType } from "../types/shift.types.js";

const ShiftTypeSchema = z.enum(["tag", "nacht", "frei", "fakt_frueh", "fakt_spaet"]);
const ShiftSourceSchema = z.enum(["voice", "dashboard", "discord", "manual"]);

const UpsertShiftSchema = z.object({
    date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, "Format: YYYY-MM-DD"),
    type: ShiftTypeSchema,
    source: ShiftSourceSchema.optional(),
    notes: z.string().max(500).optional(),
});

const RangeQuerySchema = z.object({
    from: z.string().regex(/^\d{4}-\d{2}-\d{2}$/).optional(),
    to: z.string().regex(/^\d{4}-\d{2}-\d{2}$/).optional(),
});

export async function shiftRoutes(server: FastifyInstance) {

    // GET /api/shifts — Liste mit optionalem ?from=&to=
    server.get("/api/shifts", { preHandler: requireAnyJarvisAuth }, async (req, reply) => {
        const q = RangeQuerySchema.safeParse(req.query);
        if (!q.success) return reply.code(400).send({ error: "invalid_query", details: q.error.flatten() });

        const today = getTodayDateStr();
        const from = q.data.from ?? addDaysStr(today, -30);
        const to = q.data.to ?? addDaysStr(today, 60);

        const shifts = getShiftsInRange(from, to);
        return { ok: true, count: shifts.length, from, to, shifts };
    });

    // GET /api/shifts/today
    server.get("/api/shifts/today", { preHandler: requireAnyJarvisAuth }, async () => {
        const shift = getShiftByDate(getTodayDateStr());
        return { ok: true, date: getTodayDateStr(), shift };
    });

    // GET /api/shifts/tomorrow
    server.get("/api/shifts/tomorrow", { preHandler: requireAnyJarvisAuth }, async () => {
        const shift = getShiftByDate(getTomorrowDateStr());
        return { ok: true, date: getTomorrowDateStr(), shift };
    });

    // GET /api/shifts/:date — Schicht für ein Datum
    server.get("/api/shifts/:date", { preHandler: requireAnyJarvisAuth }, async (req, reply) => {
        const { date } = req.params as { date: string };
        if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) {
            return reply.code(400).send({ error: "invalid_date_format", hint: "YYYY-MM-DD" });
        }
        const shift = getShiftByDate(date);
        if (!shift) return reply.code(404).send({ error: "shift_not_found", date });
        return { ok: true, shift };
    });

    // POST /api/shifts — Schicht eintragen (UPSERT by date)
    server.post("/api/shifts", { preHandler: requireAnyJarvisAuth }, async (req, reply) => {
        const parsed = UpsertShiftSchema.safeParse(req.body);
        if (!parsed.success) return reply.code(400).send({ error: "invalid_shift_payload", details: parsed.error.flatten() });

        const shift = upsertShift(
            parsed.data.date,
            parsed.data.type as ShiftType,
            (parsed.data.source ?? "manual") as ShiftSource,
            parsed.data.notes
        );
        return reply.code(201).send({ ok: true, shift });
    });

    // PUT /api/shifts/:id — Schicht vollständig ersetzen
    server.put("/api/shifts/:id", { preHandler: requireAnyJarvisAuth }, async (req, reply) => {
        const { id } = req.params as { id: string };
        const existing = getShiftById(id);
        if (!existing) return reply.code(404).send({ error: "shift_not_found" });

        const parsed = UpsertShiftSchema.safeParse(req.body);
        if (!parsed.success) return reply.code(400).send({ error: "invalid_shift_payload", details: parsed.error.flatten() });

        const shift = upsertShift(
            parsed.data.date,
            parsed.data.type as ShiftType,
            (parsed.data.source ?? existing.source) as ShiftSource,
            parsed.data.notes
        );
        return { ok: true, shift };
    });

    // DELETE /api/shifts/:id
    server.delete("/api/shifts/:id", { preHandler: requireAnyJarvisAuth }, async (req, reply) => {
        const { id } = req.params as { id: string };
        const ok = deleteShift(id);
        if (!ok) return reply.code(404).send({ error: "shift_not_found" });
        return { ok: true };
    });
}

// Hilfsfunktion (lokal, nicht aus shift.types wegen Kreisimport)
function addDaysStr(dateStr: string, days: number): string {
    const d = new Date(`${dateStr}T00:00:00`);
    d.setDate(d.getDate() + days);
    return d.toISOString().slice(0, 10);
}
