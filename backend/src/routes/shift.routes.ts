import type { FastifyInstance } from 'fastify';
import { z } from 'zod';
import { requireAnyJarvisAuth } from '../security/auth.js';
import {
  addDays,
  createShift,
  deleteShift,
  getShiftByDate,
  getShiftById,
  getShiftTypes,
  listShifts,
  ShiftConflictError,
  updateShift,
} from '../services/shift.service.js';
import { getAvailability } from '../services/availability.service.js';
import type { ShiftSource, ShiftType } from '../types/shift.types.js';

// ── Validation Schemas ────────────────────────────────────────────────────────

const ShiftTypeSchema = z.enum(['tag', 'nacht', 'frei', 'fakt_frueh', 'fakt_spaet']);
const ShiftSourceSchema = z.enum(['voice', 'dashboard', 'discord', 'manual']);

const CreateShiftSchema = z.object({
  date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, 'Format: YYYY-MM-DD'),
  type: ShiftTypeSchema,
  source: ShiftSourceSchema.optional(),
  notes: z.string().max(500).optional(),
  startTime: z.string().regex(/^\d{2}:\d{2}$/).optional(),
  endTime: z.string().regex(/^\d{2}:\d{2}$/).optional(),
});

const UpdateShiftSchema = z.object({
  type: ShiftTypeSchema.optional(),
  source: ShiftSourceSchema.optional(),
  notes: z.string().max(500).optional(),
  startTime: z.string().regex(/^\d{2}:\d{2}$/).optional(),
  endTime: z.string().regex(/^\d{2}:\d{2}$/).optional(),
}).refine((d) => Object.keys(d).length > 0, { message: 'Mindestens ein Feld erforderlich.' });

const RangeQuerySchema = z.object({
  from: z.string().regex(/^\d{4}-\d{2}-\d{2}$/).optional(),
  to: z.string().regex(/^\d{4}-\d{2}-\d{2}$/).optional(),
});

// ── Routes ────────────────────────────────────────────────────────────────────

export async function shiftRoutes(server: FastifyInstance) {

  // GET /api/shifts — Liste mit optionalem ?from=&to=
  server.get('/api/shifts', { preHandler: requireAnyJarvisAuth }, async (req, reply) => {
    const q = RangeQuerySchema.safeParse(req.query);
    if (!q.success)
      return reply.code(400).send({ error: 'invalid_query', details: q.error.flatten() });

    const today = todayStr();
    const from = q.data.from ?? addDays(today, -30);
    const to = q.data.to ?? addDays(today, 60);

    const shifts = listShifts(from, to);
    return { ok: true, count: shifts.length, from, to, shifts };
  });

  // GET /api/shifts/today
  server.get('/api/shifts/today', { preHandler: requireAnyJarvisAuth }, async () => {
    const today = todayStr();
    const shift = getShiftByDate(today);
    return { ok: true, date: today, shift };
  });

  // GET /api/shifts/tomorrow
  server.get('/api/shifts/tomorrow', { preHandler: requireAnyJarvisAuth }, async () => {
    const tomorrow = addDays(todayStr(), 1);
    const shift = getShiftByDate(tomorrow);
    return { ok: true, date: tomorrow, shift };
  });

  // GET /api/shifts/:date — Schicht für ein konkretes Datum
  server.get('/api/shifts/:date', { preHandler: requireAnyJarvisAuth }, async (req, reply) => {
    const { date } = req.params as { date: string };
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date))
      return reply.code(400).send({ error: 'invalid_date_format', hint: 'YYYY-MM-DD' });

    const shift = getShiftByDate(date);
    if (!shift) return reply.code(404).send({ error: 'shift_not_found', date });
    return { ok: true, shift };
  });

  // POST /api/shifts — Neue Schicht anlegen (409 bei Datum-Konflikt)
  server.post('/api/shifts', { preHandler: requireAnyJarvisAuth }, async (req, reply) => {
    const parsed = CreateShiftSchema.safeParse(req.body);
    if (!parsed.success)
      return reply.code(400).send({ error: 'invalid_shift_payload', details: parsed.error.flatten() });

    try {
      const shift = createShift({
        date: parsed.data.date,
        type: parsed.data.type as ShiftType,
        source: (parsed.data.source ?? 'manual') as ShiftSource,
        notes: parsed.data.notes,
        startTime: parsed.data.startTime,
        endTime: parsed.data.endTime,
      });
      return reply.code(201).send({ ok: true, shift });
    } catch (err) {
      if (err instanceof ShiftConflictError) {
        return reply.code(409).send({
          error: 'shift_conflict',
          message: err.message,
        });
      }
      throw err;
    }
  });

  // PATCH /api/shifts/:id — Schicht teilweise aktualisieren
  server.patch('/api/shifts/:id', { preHandler: requireAnyJarvisAuth }, async (req, reply) => {
    const { id } = req.params as { id: string };
    if (!getShiftById(id)) return reply.code(404).send({ error: 'shift_not_found' });

    const parsed = UpdateShiftSchema.safeParse(req.body);
    if (!parsed.success)
      return reply.code(400).send({ error: 'invalid_shift_payload', details: parsed.error.flatten() });

    const shift = updateShift(id, {
      type: parsed.data.type as ShiftType | undefined,
      source: parsed.data.source as ShiftSource | undefined,
      notes: parsed.data.notes,
      startTime: parsed.data.startTime,
      endTime: parsed.data.endTime,
    });
    return { ok: true, shift };
  });

  // DELETE /api/shifts/:id
  server.delete('/api/shifts/:id', { preHandler: requireAnyJarvisAuth }, async (req, reply) => {
    const { id } = req.params as { id: string };
    const ok = deleteShift(id);
    if (!ok) return reply.code(404).send({ error: 'shift_not_found' });
    return { ok: true };
  });

  // GET /api/availability/:date — Streaming-Verfügbarkeit für ein Datum
  // Optionaler Query-Param: ?current_hour=20 (0–23) für zeitabhängige Empfehlung
  server.get('/api/availability/:date', { preHandler: requireAnyJarvisAuth }, async (req, reply) => {
    const { date } = req.params as { date: string };
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date))
      return reply.code(400).send({ error: 'invalid_date_format', hint: 'YYYY-MM-DD' });

    const rawHour = (req.query as Record<string, string>).current_hour;
    const currentHour =
      rawHour !== undefined
        ? Math.max(0, Math.min(23, parseInt(rawHour, 10)))
        : new Date().getHours();

    const availability = getAvailability(date, currentHour);
    return { ok: true, availability };
  });

  // GET /api/shift-types — Alle konfigurierten Schichttypen
  server.get('/api/shift-types', { preHandler: requireAnyJarvisAuth }, async () => {
    const types = getShiftTypes();
    return { ok: true, types };
  });
}

// ── Hilfsfunktion ─────────────────────────────────────────────────────────────

function todayStr(): string {
  return new Date().toISOString().slice(0, 10);
}
