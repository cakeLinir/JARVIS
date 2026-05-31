/**
 * Einmalige Datenmigration: .runtime/data/shifts.json + todos.json → SQLite
 *
 * Ausführen (einmalig nach dem Update auf SQLite):
 *   node --import tsx src/scripts/migrate-json-to-sqlite.ts
 *
 * Idempotent: bereits vorhandene Datensätze (gleiche ID) werden übersprungen.
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { getDb } from '../services/db.js';
import { createTodo } from '../services/todo.service.js';
import { createShift, ShiftConflictError } from '../services/shift.service.js';
import type { ShiftType, ShiftSource } from '../types/shift.types.js';
import type { TodoSource, TodoStatus } from '../types/todo.types.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const RUNTIME_DIR = path.resolve(__dirname, '../../../.runtime/data');

// ── Hilfsfunktionen ───────────────────────────────────────────────────────────

function loadJson(file: string): unknown[] {
  const p = path.join(RUNTIME_DIR, file);
  if (!fs.existsSync(p)) {
    console.log(`  ℹ  ${file} nicht gefunden — übersprungen.`);
    return [];
  }
  try {
    const raw = JSON.parse(fs.readFileSync(p, 'utf-8'));
    return Array.isArray(raw) ? raw : (raw?.todos ?? raw?.shifts ?? []);
  } catch (err) {
    console.error(`  ✗ ${file} konnte nicht gelesen werden: ${err}`);
    return [];
  }
}

// ── TODO-Migration ─────────────────────────────────────────────────────────────

function migrateTodos(): void {
  const todos = loadJson('todos.json') as Record<string, unknown>[];
  if (todos.length === 0) return;

  console.log(`\n── TODOs migrieren (${todos.length} Einträge) ─────────────────`);

  const db = getDb();
  let created = 0;
  let skipped = 0;

  for (const t of todos) {
    const id = String(t.id ?? '');
    if (!id || !t.title) { skipped++; continue; }

    // Bereits vorhanden?
    const existing = db.prepare('SELECT id FROM todos WHERE id = ?').get(id);
    if (existing) { skipped++; continue; }

    try {
      // createTodo generiert eine neue ID — wir müssen die alte beibehalten
      db.prepare(`
        INSERT INTO todos (
          id, title, description, status, priority, category,
          due_date, due_time, start_date, recurrence, reminder_min,
          shift_id, source, created_at, updated_at, completed_at, history
        ) VALUES (
          @id, @title, @description, @status, @priority, @category,
          @due_date, @due_time, @start_date, @recurrence, @reminder_min,
          @shift_id, @source, @created_at, @updated_at, @completed_at, @history
        )
      `).run({
        id,
        title:        String(t.title ?? ''),
        description:  String(t.description ?? ''),
        status:       String(t.status ?? 'open'),
        priority:     Number(t.priority ?? 3),
        category:     String(t.category ?? ''),
        due_date:     t.dueDate ?? null,
        due_time:     t.dueTime ?? null,
        start_date:   t.startDate ?? null,
        recurrence:   t.recurrence ? JSON.stringify(t.recurrence) : 'none',
        reminder_min: t.reminderMinutes ?? null,
        shift_id:     t.shiftId ?? null,
        source:       String(t.source ?? 'manual'),
        created_at:   String(t.createdAt ?? new Date().toISOString()),
        updated_at:   String(t.updatedAt ?? new Date().toISOString()),
        completed_at: t.completedAt ?? null,
        history:      JSON.stringify(t.history ?? []),
      });
      console.log(`  ✓ TODO: ${t.title}`);
      created++;
    } catch (err) {
      console.error(`  ✗ TODO-Fehler (${t.title}): ${err}`);
      skipped++;
    }
  }

  console.log(`  → ${created} migriert, ${skipped} übersprungen.`);
}

// ── Schicht-Migration ──────────────────────────────────────────────────────────

function migrateShifts(): void {
  const shifts = loadJson('shifts.json') as Record<string, unknown>[];
  if (shifts.length === 0) return;

  console.log(`\n── Schichten migrieren (${shifts.length} Einträge) ────────────`);

  let created = 0;
  let skipped = 0;

  for (const s of shifts) {
    const date   = String(s.date ?? '');
    const type   = String(s.type ?? '') as ShiftType;
    const source = String(s.source ?? 'manual') as ShiftSource;

    if (!date || !type) { skipped++; continue; }

    try {
      createShift({
        date,
        type,
        source,
        notes:     s.notes ? String(s.notes) : undefined,
        startTime: s.startTime ? String(s.startTime) : undefined,
        endTime:   s.endTime   ? String(s.endTime)   : undefined,
      });
      console.log(`  ✓ Schicht: ${date} ${type}`);
      created++;
    } catch (err) {
      if (err instanceof ShiftConflictError) {
        skipped++;  // Datum bereits vorhanden
      } else {
        console.error(`  ✗ Schicht-Fehler (${date}): ${err}`);
        skipped++;
      }
    }
  }

  console.log(`  → ${created} migriert, ${skipped} übersprungen (inkl. Konflikte).`);
}

// ── Main ───────────────────────────────────────────────────────────────────────

console.log('\n══ JARVIS JSON → SQLite Migration ════════════════════════════\n');
console.log(`  Quelle: ${RUNTIME_DIR}`);

migrateTodos();
migrateShifts();

console.log('\n══ Migration abgeschlossen ════════════════════════════════════\n');
