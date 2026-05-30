import { getDb } from './db.js';
import { appendAuditEvent } from './audit-log.js';
import {
  addDays,
  createShiftId,
  SHIFT_DEFINITIONS,
  type JarvisShift,
  type ShiftSource,
  type ShiftType,
} from '../types/shift.types.js';

// ── Typen ─────────────────────────────────────────────────────────────────────

export type CreateShiftInput = {
  date: string;
  type: ShiftType;
  source?: ShiftSource;
  notes?: string;
  startTime?: string;
  endTime?: string;
};

export type UpdateShiftInput = {
  type?: ShiftType;
  source?: ShiftSource;
  notes?: string;
  startTime?: string;
  endTime?: string;
};

export type ShiftTypeRecord = {
  type: string;
  label: string;
  defaultStart: string | null;
  defaultEnd: string | null;
  crossesMidnight: boolean;
  restHoursBefore: number;
  restHoursAfter: number;
  streamRecommendation: string;
  streamReason: string;
};

// Wird in den Routen gefangen und als HTTP 409 gesendet
export class ShiftConflictError extends Error {
  constructor(date: string) {
    super(`Schicht für ${date} bereits vorhanden`);
    this.name = 'ShiftConflictError';
  }
}

// ── DB-Row → JarvisShift ──────────────────────────────────────────────────────

type ShiftRow = {
  id: string;
  date: string;
  type: string;
  start_time: string | null;
  end_time: string | null;
  crosses_midnight: number;
  end_date: string | null;
  notes: string;
  source: string;
  created_at: string;
  updated_at: string;
};

function rowToShift(row: ShiftRow): JarvisShift {
  const def = SHIFT_DEFINITIONS[row.type as Exclude<ShiftType, 'custom'>];
  return {
    id: row.id,
    date: row.date,
    type: row.type as ShiftType,
    startTime: row.start_time ?? def?.startTime ?? '00:00',
    endTime: row.end_time ?? def?.endTime ?? '00:00',
    overnight: row.crosses_midnight === 1,
    endDate: row.end_date ?? undefined,
    label: def?.label ?? row.type,
    source: row.source as ShiftSource,
    notes: row.notes || undefined,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
  };
}

// ── Lese-Operationen ──────────────────────────────────────────────────────────

export function getShiftById(id: string): JarvisShift | null {
  const db = getDb();
  const row = db.prepare('SELECT * FROM shifts WHERE id = ?').get(id) as ShiftRow | undefined;
  return row ? rowToShift(row) : null;
}

export function getShiftByDate(date: string): JarvisShift | null {
  const db = getDb();
  const row = db.prepare('SELECT * FROM shifts WHERE date = ?').get(date) as ShiftRow | undefined;
  return row ? rowToShift(row) : null;
}

export function listShifts(from: string, to: string): JarvisShift[] {
  const db = getDb();
  const rows = db
    .prepare('SELECT * FROM shifts WHERE date >= @from AND date <= @to ORDER BY date ASC')
    .all({ from, to }) as ShiftRow[];
  return rows.map(rowToShift);
}

export function getShiftTypes(): ShiftTypeRecord[] {
  const db = getDb();
  type TypeRow = {
    type: string;
    label: string;
    default_start: string | null;
    default_end: string | null;
    crosses_midnight: number;
    rest_hours_before: number;
    rest_hours_after: number;
    stream_recommendation: string;
    stream_reason: string;
  };
  const rows = db.prepare('SELECT * FROM shift_types ORDER BY type').all() as TypeRow[];
  return rows.map((r) => ({
    type: r.type,
    label: r.label,
    defaultStart: r.default_start,
    defaultEnd: r.default_end,
    crossesMidnight: r.crosses_midnight === 1,
    restHoursBefore: r.rest_hours_before,
    restHoursAfter: r.rest_hours_after,
    streamRecommendation: r.stream_recommendation,
    streamReason: r.stream_reason,
  }));
}

// ── Schreib-Operationen ───────────────────────────────────────────────────────

// Conflict-Check: wirft ShiftConflictError wenn Datum bereits belegt
export function createShift(input: CreateShiftInput): JarvisShift {
  const db = getDb();

  const existing = db
    .prepare('SELECT id FROM shifts WHERE date = ?')
    .get(input.date) as { id: string } | undefined;

  if (existing) {
    throw new ShiftConflictError(input.date);
  }

  const now = new Date().toISOString();
  const id = createShiftId();
  const type = input.type;

  // Defaults aus SHIFT_DEFINITIONS, überschreibbar durch Input
  const def = type !== 'custom' ? SHIFT_DEFINITIONS[type] : null;
  const startTime = input.startTime ?? def?.startTime ?? null;
  const endTime = input.endTime ?? def?.endTime ?? null;
  const overnight = def?.overnight ?? false;
  const endDate = overnight ? addDays(input.date, 1) : null;

  db.prepare(
    `INSERT INTO shifts (
       id, date, type, start_time, end_time,
       crosses_midnight, end_date, notes, source, created_at, updated_at
     ) VALUES (
       @id, @date, @type, @start_time, @end_time,
       @crosses_midnight, @end_date, @notes, @source, @created_at, @updated_at
     )`,
  ).run({
    id,
    date: input.date,
    type,
    start_time: startTime,
    end_time: endTime,
    crosses_midnight: overnight ? 1 : 0,
    end_date: endDate,
    notes: input.notes ?? '',
    source: input.source ?? 'manual',
    created_at: now,
    updated_at: now,
  });

  appendAuditEvent({
    component: 'shift.service',
    action: 'shift.create',
    result: 'completed',
    message: `Schicht eingetragen: ${input.date} → ${def?.label ?? type}`,
    details: { id, date: input.date, type, source: input.source },
  });

  return getShiftById(id)!;
}

export function updateShift(id: string, data: UpdateShiftInput): JarvisShift | null {
  const existing = getShiftById(id);
  if (!existing) return null;

  const db = getDb();
  const now = new Date().toISOString();

  // Bei Typwechsel neue Defaults ermitteln
  const newType = data.type ?? existing.type;
  const def = newType !== 'custom' ? SHIFT_DEFINITIONS[newType as Exclude<ShiftType, 'custom'>] : null;
  const overnight = def?.overnight ?? existing.overnight;
  const endDate = overnight ? addDays(existing.date, 1) : null;

  db.prepare(
    `UPDATE shifts SET
       type             = @type,
       start_time       = @start_time,
       end_time         = @end_time,
       crosses_midnight = @crosses_midnight,
       end_date         = @end_date,
       notes            = @notes,
       source           = @source,
       updated_at       = @updated_at
     WHERE id = @id`,
  ).run({
    id,
    type: newType,
    start_time: data.startTime ?? (def?.startTime ?? existing.startTime),
    end_time: data.endTime ?? (def?.endTime ?? existing.endTime),
    crosses_midnight: overnight ? 1 : 0,
    end_date: endDate,
    notes: data.notes !== undefined ? data.notes : (existing.notes ?? ''),
    source: data.source ?? existing.source,
    updated_at: now,
  });

  appendAuditEvent({
    component: 'shift.service',
    action: 'shift.update',
    result: 'completed',
    message: `Schicht geändert: ${existing.date}`,
    details: { id, changes: data },
  });

  return getShiftById(id)!;
}

export function deleteShift(id: string): boolean {
  const existing = getShiftById(id);
  if (!existing) return false;

  const db = getDb();
  db.prepare('DELETE FROM shifts WHERE id = ?').run(id);

  appendAuditEvent({
    component: 'shift.service',
    action: 'shift.delete',
    result: 'completed',
    message: `Schicht gelöscht: ${existing.date} ${existing.label}`,
    details: { id, date: existing.date },
  });

  return true;
}

// Hilfsfunktion für Datumsoperationen (re-export für Routen)
export { addDays };
