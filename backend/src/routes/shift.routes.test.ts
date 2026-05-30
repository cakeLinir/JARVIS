/**
 * Schicht-Service-Tests — ohne echte Backend-Verbindung (In-Memory SQLite).
 * Ausführen: node --import tsx --test src/routes/shift.routes.test.ts
 */

import { test, describe, before, after, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { _setTestDb, createTestDb } from '../services/db.js';
import {
  createShift,
  deleteShift,
  getShiftByDate,
  getShiftById,
  listShifts,
  ShiftConflictError,
} from '../services/shift.service.js';
import { computeAvailability } from '../services/availability.service.js';
import type Database from 'better-sqlite3';

let testDb: Database.Database;

// ── Test-Setup ────────────────────────────────────────────────────────────────

before(() => {
  testDb = createTestDb();
  _setTestDb(testDb);
});

after(() => {
  _setTestDb(null);
  testDb?.close();
});

beforeEach(() => {
  testDb.exec('DELETE FROM shifts');
});

// ── Tests ─────────────────────────────────────────────────────────────────────

describe('createShift', () => {

  test('legt Tagschicht an und gibt ID zurück', () => {
    const shift = createShift({ date: '2026-07-01', type: 'tag', source: 'dashboard' });

    assert.ok(shift.id, 'id muss vorhanden sein');
    assert.equal(shift.date, '2026-07-01');
    assert.equal(shift.type, 'tag');
    assert.equal(shift.startTime, '07:00');
    assert.equal(shift.endTime, '19:00');
    assert.equal(shift.overnight, false);
    assert.equal(shift.endDate, undefined);
  });

  test('Nachtschicht hat crosses_midnight=true und end_date = start_date + 1', () => {
    const shift = createShift({ date: '2026-07-01', type: 'nacht' });

    assert.equal(shift.type, 'nacht');
    assert.equal(shift.overnight, true);
    assert.equal(shift.endDate, '2026-07-02');  // start_date + 1
    assert.equal(shift.startTime, '19:00');
    assert.equal(shift.endTime, '07:00');
  });

  test('FAKT-Früh hat korrekte Zeiten', () => {
    const shift = createShift({ date: '2026-07-02', type: 'fakt_frueh' });

    assert.equal(shift.startTime, '07:00');
    assert.equal(shift.endTime, '14:30');
    assert.equal(shift.overnight, false);
  });

  test('doppelte Schicht am gleichen Tag → 409 ShiftConflictError', () => {
    createShift({ date: '2026-07-03', type: 'tag' });

    assert.throws(
      () => createShift({ date: '2026-07-03', type: 'frei' }),
      (err: unknown) => {
        assert.ok(err instanceof ShiftConflictError, 'muss ShiftConflictError sein');
        assert.ok((err as Error).message.includes('2026-07-03'));
        return true;
      },
    );
  });

  test('Frei-Schicht hat keine Zeiten', () => {
    const shift = createShift({ date: '2026-07-04', type: 'frei' });

    // Frei hat NULL-Zeiten in shift_types, startTime fällt auf '00:00' zurück
    assert.equal(shift.overnight, false);
    assert.equal(shift.endDate, undefined);
  });
});

describe('getShiftByDate', () => {

  test('gibt Schicht für Datum zurück', () => {
    createShift({ date: '2026-08-01', type: 'nacht' });
    const found = getShiftByDate('2026-08-01');

    assert.ok(found, 'muss gefunden werden');
    assert.equal(found?.type, 'nacht');
  });

  test('gibt null zurück für leeres Datum', () => {
    const result = getShiftByDate('2099-01-01');
    assert.equal(result, null);
  });
});

describe('deleteShift', () => {

  test('löscht Schicht und gibt true zurück', () => {
    const shift = createShift({ date: '2026-09-01', type: 'tag' });
    const result = deleteShift(shift.id);

    assert.equal(result, true);
    assert.equal(getShiftByDate('2026-09-01'), null);
  });

  test('gibt false für unbekannte ID zurück', () => {
    const result = deleteShift('nicht-vorhanden-xyz');
    assert.equal(result, false);
  });
});

describe('listShifts', () => {

  test('listet Schichten im Datumsbereich', () => {
    createShift({ date: '2026-10-01', type: 'tag' });
    createShift({ date: '2026-10-02', type: 'frei' });
    createShift({ date: '2026-10-03', type: 'nacht' });

    const result = listShifts('2026-10-01', '2026-10-02');
    assert.equal(result.length, 2);
    assert.equal(result[0].date, '2026-10-01');  // sortiert nach Datum
  });

  test('gibt leere Liste zurück für Bereich ohne Schichten', () => {
    const result = listShifts('2099-01-01', '2099-01-07');
    assert.equal(result.length, 0);
  });
});

describe('computeAvailability (Availability-Regelwerk)', () => {

  test('freier Tag → streamRecommendation = free', () => {
    const frei = { id: 'f1', date: '2026-07-01', type: 'frei' as const, startTime: '00:00',
      endTime: '23:59', overnight: false, label: 'Frei', source: 'manual' as const,
      createdAt: '', updatedAt: '' };

    const result = computeAvailability('2026-07-01', frei, null, null, 14);
    assert.equal(result.streamRecommendation, 'free');
    assert.ok(result.streamWindow, 'freier Tag muss Fenster haben');
  });

  test('Nachtschicht um 19 Uhr → vor 12 Uhr bedingt möglich', () => {
    const nacht = { id: 'n1', date: '2026-07-02', type: 'nacht' as const, startTime: '19:00',
      endTime: '07:00', overnight: true, endDate: '2026-07-03', label: 'Nachtschicht',
      source: 'manual' as const, createdAt: '', updatedAt: '' };

    const result = computeAvailability('2026-07-02', nacht, null, null, 10);
    assert.equal(result.streamRecommendation, 'conditional');
    assert.deepEqual(result.streamWindow, { from: '10:00', to: '12:00' });
  });

  test('Nachtschicht um 19 Uhr → ab 17 Uhr blockiert', () => {
    const nacht = { id: 'n2', date: '2026-07-02', type: 'nacht' as const, startTime: '19:00',
      endTime: '07:00', overnight: true, endDate: '2026-07-03', label: 'Nachtschicht',
      source: 'manual' as const, createdAt: '', updatedAt: '' };

    const result = computeAvailability('2026-07-02', nacht, null, null, 18);
    assert.equal(result.streamRecommendation, 'blocked');
    assert.equal(result.streamWindow, null);
  });

  test('Recovery nach Nacht → vor 14 Uhr blockiert', () => {
    const prevNacht = { id: 'pn', date: '2026-07-01', type: 'nacht' as const,
      startTime: '19:00', endTime: '07:00', overnight: true, endDate: '2026-07-02',
      label: 'Nachtschicht', source: 'manual' as const, createdAt: '', updatedAt: '' };

    const result = computeAvailability('2026-07-02', null, prevNacht, null, 9);
    assert.equal(result.streamRecommendation, 'blocked');
  });

  test('Kein Eintrag, morgen Tagschicht → abends conditional', () => {
    const nextTag = { id: 't1', date: '2026-07-03', type: 'tag' as const, startTime: '07:00',
      endTime: '19:00', overnight: false, label: 'Tagschicht', source: 'manual' as const,
      createdAt: '', updatedAt: '' };

    const result = computeAvailability('2026-07-02', null, null, nextTag, 18);
    assert.equal(result.streamRecommendation, 'conditional');
  });

  test('currentHour ist im Ergebnis enthalten', () => {
    const result = computeAvailability('2026-07-01', null, null, null, 15);
    assert.equal(result.currentHour, 15);
  });
});
