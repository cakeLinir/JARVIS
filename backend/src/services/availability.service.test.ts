// Unit-Tests für computeAvailability — kein DB-Zugriff erforderlich.
// Ausführen: node --import tsx --test src/services/availability.service.test.ts

import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { computeAvailability } from './availability.service.js';
import type { JarvisShift, ShiftType } from '../types/shift.types.js';

// ── Test-Fixtures ─────────────────────────────────────────────────────────────

const DATE      = '2026-06-10';
const PREV_DATE = '2026-06-09';
const NEXT_DATE = '2026-06-11';

const SHIFT_DEFS: Record<Exclude<ShiftType, 'custom'>, { start: string; end: string; overnight: boolean; label: string }> = {
  tag:        { start: '07:00', end: '19:00', overnight: false, label: 'Tagschicht' },
  nacht:      { start: '19:00', end: '07:00', overnight: true,  label: 'Nachtschicht' },
  frei:       { start: '00:00', end: '23:59', overnight: false, label: 'Frei' },
  fakt_frueh: { start: '07:00', end: '14:30', overnight: false, label: 'FAKT IST! Früh' },
  fakt_spaet: { start: '14:30', end: '21:30', overnight: false, label: 'FAKT IST! Spät' },
};

function shift(type: Exclude<ShiftType, 'custom'>, date = DATE): JarvisShift {
  const d = SHIFT_DEFS[type];
  const now = new Date().toISOString();
  return {
    id: `test_${type}`,
    date,
    type,
    startTime: d.start,
    endTime: d.end,
    overnight: d.overnight,
    endDate: d.overnight ? NEXT_DATE : undefined,
    label: d.label,
    source: 'manual',
    createdAt: now,
    updatedAt: now,
  };
}

// Nachtschicht auf PREV_DATE die auf DATE endet (Recovery-Szenario)
function prevNacht(): JarvisShift {
  const d = SHIFT_DEFS.nacht;
  const now = new Date().toISOString();
  return {
    id: 'test_nacht_prev',
    date: PREV_DATE,
    type: 'nacht',
    startTime: d.start,
    endTime: d.end,
    overnight: true,
    endDate: DATE,   // endet auf DATE
    label: d.label,
    source: 'manual',
    createdAt: now,
    updatedAt: now,
  };
}

// ── FREI ──────────────────────────────────────────────────────────────────────

describe('FREI', () => {
  const s = shift('frei');

  it('morgens → free', () => {
    const r = computeAvailability(DATE, s, null, null, 9);
    assert.equal(r.streamRecommendation, 'free');
    assert.notEqual(r.streamWindow, null);
  });

  it('nachmittags → free', () => {
    const r = computeAvailability(DATE, s, null, null, 15);
    assert.equal(r.streamRecommendation, 'free');
  });

  it('nachts → free', () => {
    const r = computeAvailability(DATE, s, null, null, 23);
    assert.equal(r.streamRecommendation, 'free');
  });
});

// ── TAGSCHICHT ────────────────────────────────────────────────────────────────

describe('TAGSCHICHT', () => {
  const s = shift('tag');

  it('06:00 (vor Schicht) → discouraged, kein Fenster', () => {
    const r = computeAvailability(DATE, s, null, null, 6);
    assert.equal(r.streamRecommendation, 'discouraged');
    assert.equal(r.streamWindow, null);
  });

  it('10:00 (während Schicht) → blocked, kein Fenster', () => {
    const r = computeAvailability(DATE, s, null, null, 10);
    assert.equal(r.streamRecommendation, 'blocked');
    assert.equal(r.streamWindow, null);
  });

  it('18:00 (letzte Stunde Schicht) → blocked', () => {
    const r = computeAvailability(DATE, s, null, null, 18);
    assert.equal(r.streamRecommendation, 'blocked');
  });

  it('20:00 (nach Schicht) → conditional, Fenster 19–22', () => {
    const r = computeAvailability(DATE, s, null, null, 20);
    assert.equal(r.streamRecommendation, 'conditional');
    assert.deepEqual(r.streamWindow, { from: '19:00', to: '22:00' });
  });

  it('22:00 (spät nach Schicht) → discouraged', () => {
    const r = computeAvailability(DATE, s, null, null, 22);
    assert.equal(r.streamRecommendation, 'discouraged');
    assert.equal(r.streamWindow, null);
  });
});

// ── NACHTSCHICHT ──────────────────────────────────────────────────────────────

describe('NACHTSCHICHT', () => {
  const s = shift('nacht');

  it('10:00 (morgens) → conditional, Fenster 10–12', () => {
    const r = computeAvailability(DATE, s, null, null, 10);
    assert.equal(r.streamRecommendation, 'conditional');
    assert.deepEqual(r.streamWindow, { from: '10:00', to: '12:00' });
  });

  it('14:00 (nachmittags) → discouraged, kein Fenster', () => {
    const r = computeAvailability(DATE, s, null, null, 14);
    assert.equal(r.streamRecommendation, 'discouraged');
    assert.equal(r.streamWindow, null);
  });

  it('19:00 (Schicht aktiv) → blocked', () => {
    const r = computeAvailability(DATE, s, null, null, 19);
    assert.equal(r.streamRecommendation, 'blocked');
    assert.equal(r.streamWindow, null);
  });
});

// ── FAKT IST! FRÜH ────────────────────────────────────────────────────────────

describe('FAKT_FRUEH', () => {
  const s = shift('fakt_frueh');

  it('06:00 (vor Schicht) → discouraged', () => {
    const r = computeAvailability(DATE, s, null, null, 6);
    assert.equal(r.streamRecommendation, 'discouraged');
  });

  it('10:00 (während Schicht) → blocked', () => {
    const r = computeAvailability(DATE, s, null, null, 10);
    assert.equal(r.streamRecommendation, 'blocked');
    assert.equal(r.streamWindow, null);
  });

  it('16:00 (nach Schicht) → conditional, ab 14:30', () => {
    const r = computeAvailability(DATE, s, null, null, 16);
    assert.equal(r.streamRecommendation, 'conditional');
    assert.equal(r.streamWindow?.from, '14:30');
    assert.equal(r.streamWindow?.to, '22:00');
  });

  it('22:00 (spät) → discouraged', () => {
    const r = computeAvailability(DATE, s, null, null, 22);
    assert.equal(r.streamRecommendation, 'discouraged');
  });
});

// ── FAKT IST! SPÄT ───────────────────────────────────────────────────────────

describe('FAKT_SPAET', () => {
  const s = shift('fakt_spaet');

  it('09:00 (morgens vor Schicht) → conditional, bis 12 Uhr', () => {
    const r = computeAvailability(DATE, s, null, null, 9);
    assert.equal(r.streamRecommendation, 'conditional');
    assert.deepEqual(r.streamWindow, { from: '10:00', to: '12:00' });
  });

  it('13:00 (kurz vor Schicht) → discouraged', () => {
    const r = computeAvailability(DATE, s, null, null, 13);
    assert.equal(r.streamRecommendation, 'discouraged');
    assert.equal(r.streamWindow, null);
  });

  it('17:00 (während Schicht) → blocked', () => {
    const r = computeAvailability(DATE, s, null, null, 17);
    assert.equal(r.streamRecommendation, 'blocked');
    assert.equal(r.streamWindow, null);
  });

  it('22:00 (nach Schicht) → conditional, Fenster 21:30–23:00', () => {
    const r = computeAvailability(DATE, s, null, null, 22);
    assert.equal(r.streamRecommendation, 'conditional');
    assert.deepEqual(r.streamWindow, { from: '21:30', to: '23:00' });
  });

  it('23:00 (spät nachts) → discouraged', () => {
    const r = computeAvailability(DATE, s, null, null, 23);
    assert.equal(r.streamRecommendation, 'discouraged');
  });
});

// ── RECOVERY NACH NACHT ───────────────────────────────────────────────────────

describe('Recovery nach Nachtschicht', () => {
  const prev = prevNacht();

  it('09:00 (noch schlafen) → blocked', () => {
    const r = computeAvailability(DATE, null, prev, null, 9);
    assert.equal(r.streamRecommendation, 'blocked');
    assert.equal(r.streamWindow, null);
  });

  it('15:00 (wach nach Schlaf) → conditional, 14–18 Uhr', () => {
    const r = computeAvailability(DATE, null, prev, null, 15);
    assert.equal(r.streamRecommendation, 'conditional');
    assert.deepEqual(r.streamWindow, { from: '14:00', to: '18:00' });
  });

  it('20:00 (abends) → discouraged', () => {
    const r = computeAvailability(DATE, null, prev, null, 20);
    assert.equal(r.streamRecommendation, 'discouraged');
    assert.equal(r.streamWindow, null);
  });
});

// ── ABEND VOR (kein Eintrag, morgen Schicht) ──────────────────────────────────

describe('Abend DAVOR — kein Eintrag heute', () => {

  it('17:00, morgen Tagschicht → conditional 17–22 Uhr', () => {
    const r = computeAvailability(DATE, null, null, shift('tag', NEXT_DATE), 17);
    assert.equal(r.streamRecommendation, 'conditional');
    assert.deepEqual(r.streamWindow, { from: '17:00', to: '22:00' });
  });

  it('22:00, morgen Tagschicht → discouraged', () => {
    const r = computeAvailability(DATE, null, null, shift('tag', NEXT_DATE), 22);
    assert.equal(r.streamRecommendation, 'discouraged');
    assert.equal(r.streamWindow, null);
  });

  it('12:00, morgen Nachtschicht → conditional tagsüber', () => {
    const r = computeAvailability(DATE, null, null, shift('nacht', NEXT_DATE), 12);
    assert.equal(r.streamRecommendation, 'conditional');
  });

  it('19:00, morgen Nachtschicht → conditional 17–22 Uhr', () => {
    const r = computeAvailability(DATE, null, null, shift('nacht', NEXT_DATE), 19);
    assert.equal(r.streamRecommendation, 'conditional');
    assert.deepEqual(r.streamWindow, { from: '17:00', to: '22:00' });
  });

  it('10:00, morgen Fakt-Spät → conditional', () => {
    const r = computeAvailability(DATE, null, null, shift('fakt_spaet', NEXT_DATE), 10);
    assert.equal(r.streamRecommendation, 'conditional');
  });

  it('kein Kontext → conditional, großes Fenster', () => {
    const r = computeAvailability(DATE, null, null, null, 14);
    assert.equal(r.streamRecommendation, 'conditional');
    assert.notEqual(r.streamWindow, null);
  });
});

// ── Invarianten ───────────────────────────────────────────────────────────────

describe('Invarianten', () => {
  it('blocked hat immer streamWindow = null', () => {
    const cases = [
      computeAvailability(DATE, shift('tag'), null, null, 12),
      computeAvailability(DATE, shift('nacht'), null, null, 20),
      computeAvailability(DATE, shift('fakt_frueh'), null, null, 10),
      computeAvailability(DATE, shift('fakt_spaet'), null, null, 18),
      computeAvailability(DATE, null, prevNacht(), null, 8),
    ];
    for (const r of cases) {
      if (r.streamRecommendation === 'blocked') {
        assert.equal(r.streamWindow, null, `blocked sollte kein Fenster haben: ${r.reason}`);
      }
    }
  });

  it('free hat immer streamWindow != null', () => {
    const r = computeAvailability(DATE, shift('frei'), null, null, 14);
    assert.equal(r.streamRecommendation, 'free');
    assert.notEqual(r.streamWindow, null);
  });

  it('currentHour ist im Ergebnis enthalten', () => {
    const r = computeAvailability(DATE, shift('tag'), null, null, 15);
    assert.equal(r.currentHour, 15);
  });
});
