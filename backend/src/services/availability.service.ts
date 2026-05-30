import { addDays, type JarvisShift } from '../types/shift.types.js';
import { getShiftByDate } from './shift.service.js';

// ── Typen ─────────────────────────────────────────────────────────────────────

export type StreamRecommendation = 'free' | 'conditional' | 'discouraged' | 'blocked';

export type AvailabilityShift = {
  type: string;
  label: string;
  start: string | null;
  end: string | null;
  crossesMidnight: boolean;
};

export type StreamWindow = {
  from: string;
  to: string;
};

export type AvailabilityResult = {
  date: string;
  shift: AvailabilityShift | null;
  streamRecommendation: StreamRecommendation;
  streamWindow: StreamWindow | null;  // null wenn blocked oder kein sinnvolles Fenster
  reason: string;
  restHoursBefore: number;
  restHoursAfter: number;
  currentHour: number;
};

// ── Interne Hilfsfunktionen ───────────────────────────────────────────────────

function toAvailShift(s: JarvisShift | null): AvailabilityShift | null {
  if (!s) return null;
  return {
    type: s.type,
    label: s.label,
    start: s.startTime,
    end: s.endTime,
    crossesMidnight: s.overnight,
  };
}

function w(from: string, to: string): StreamWindow {
  return { from, to };
}

function make(
  date: string,
  shift: JarvisShift | null,
  rec: StreamRecommendation,
  window: StreamWindow | null,
  reason: string,
  restBefore: number,
  restAfter: number,
  currentHour: number,
): AvailabilityResult {
  return {
    date,
    shift: toAvailShift(shift),
    streamRecommendation: rec,
    streamWindow: window,
    reason,
    restHoursBefore: restBefore,
    restHoursAfter: restAfter,
    currentHour,
  };
}

// ── Kern-Regelwerk (pure function — ohne DB-Zugriff, vollständig testbar) ─────

export function computeAvailability(
  date: string,
  shift: JarvisShift | null,
  prevShift: JarvisShift | null,
  nextShift: JarvisShift | null,
  currentHour: number,
): AvailabilityResult {
  const h = currentHour;

  // ── Recovery-Tag nach Nachtschicht ──────────────────────────────────────────
  // Vorherige Nacht endete heute früh um 07:00 auf diesem Datum
  const isRecovery =
    prevShift?.type === 'nacht' && prevShift.overnight && prevShift.endDate === date;

  if (isRecovery) {
    // Spec: Nacht Nach 07–14 → blocked | 14–18 → conditional | ab 18 → discouraged
    if (h < 14) {
      return make(date, prevShift, 'blocked', null,
        'Nach der Nacht erst schlafen. 🛌', 8, 8, h);
    }
    if (h < 18) {
      return make(date, prevShift, 'conditional', w('14:00', '18:00'),
        'Nach dem Schlaf nach Nachtschicht — kurzer Stream ok. 🟡', 8, 8, h);
    }
    return make(date, prevShift, 'discouraged', null,
      'Erholung nach Nachtschicht — lieber früh ins Bett. 🟠', 8, 8, h);
  }

  // ── FREI ────────────────────────────────────────────────────────────────────
  if (shift?.type === 'frei') {
    return make(date, shift, 'free', w('10:00', '02:00'),
      'Freier Tag — Stream jederzeit möglich. 🟢', 0, 0, h);
  }

  // ── TAGSCHICHT 07:00–19:00 ───────────────────────────────────────────────────
  if (shift?.type === 'tag') {
    // Früh morgens: schlafen statt streamen
    if (h < 7) {
      return make(date, shift, 'discouraged', null,
        'Tagschicht beginnt um 07:00 — jetzt schlafen, nicht streamen. 🟠', 8, 8, h);
    }
    // Während Schicht
    if (h < 19) {
      return make(date, shift, 'blocked', null,
        'Tagschicht aktiv (07:00–19:00) — kein Stream. 🔴', 8, 8, h);
    }
    // Nach Schicht: kurzes Fenster bis 22 Uhr
    if (h < 22) {
      return make(date, shift, 'conditional', w('19:00', '22:00'),
        'Nach der Tagschicht — kurzer entspannter Stream bis 22 Uhr. 🟡', 8, 8, h);
    }
    // Nach 22 Uhr: schlafen
    return make(date, shift, 'discouraged', null,
      'Nach 22 Uhr — morgen früh Tagschicht endet heute, aber lieber schlafen. 🟠', 8, 8, h);
  }

  // ── NACHTSCHICHT 19:00–07:00+1 ──────────────────────────────────────────────
  if (shift?.type === 'nacht') {
    // Morgens genießen, aber Mittag schon Ruhe einplanen
    if (h < 12) {
      return make(date, shift, 'conditional', w('10:00', '12:00'),
        'Nachtschicht heute Abend — Morgen genießen, Mittag Ruhe einplanen. 🟡', 8, 8, h);
    }
    // Nachmittag: Ruhe vor der Nacht
    if (h < 17) {
      return make(date, shift, 'discouraged', null,
        'Nachtschicht heute Abend um 19 — nachmittags Ruhe für die Nacht. 🟠', 8, 8, h);
    }
    // Ab 17 Uhr: Vorbereitung / aktiv
    return make(date, shift, 'blocked', null,
      'Nachtschicht in Kürze / aktiv — kein Stream. 🔴', 8, 8, h);
  }

  // ── FAKT IST! FRÜH 07:00–14:30 ──────────────────────────────────────────────
  if (shift?.type === 'fakt_frueh') {
    // Vor Schicht: schlafen
    if (h < 7) {
      return make(date, shift, 'discouraged', null,
        'FAKT IST! Früh beginnt um 07:00 — jetzt schlafen. 🟠', 8, 8, h);
    }
    // Während Schicht (bis 14:30 → stundenmäßig < 15)
    if (h < 15) {
      return make(date, shift, 'blocked', null,
        'FAKT IST! Früh aktiv (07:00–14:30) — kein Stream. 🔴', 8, 8, h);
    }
    // Nach Schicht: Nachmittag und Abend verfügbar bis 22 Uhr
    if (h < 22) {
      return make(date, shift, 'conditional', w('14:30', '22:00'),
        'FAKT IST! Früh beendet — Nachmittag/Abend für Stream verfügbar. 🟡', 8, 8, h);
    }
    // Ab 22 Uhr: discouraged
    return make(date, shift, 'discouraged', null,
      'Nach 22 Uhr — lieber schlafen für morgen. 🟠', 8, 8, h);
  }

  // ── FAKT IST! SPÄT 14:30–21:30 ──────────────────────────────────────────────
  if (shift?.type === 'fakt_spaet') {
    // Morgens: Stream vor der Schicht
    if (h < 12) {
      return make(date, shift, 'conditional', w('10:00', '12:00'),
        'FAKT IST! Spät erst um 14:30 — Morgen für Stream verfügbar. 🟡', 8, 6, h);
    }
    // Kurz vor Schicht: Ruhe
    if (h < 15) {
      return make(date, shift, 'discouraged', null,
        'Spätschicht in Kürze — besser ausruhen. 🟠', 8, 6, h);
    }
    // Während Schicht (14:30–21:30 → stundenmäßig < 22)
    if (h < 22) {
      return make(date, shift, 'blocked', null,
        'FAKT IST! Spät aktiv (14:30–21:30) — kein Stream. 🔴', 8, 6, h);
    }
    // Kurz nach Schicht: kleines Fenster bis 23 Uhr
    if (h < 23) {
      return make(date, shift, 'conditional', w('21:30', '23:00'),
        'Nach Spätschicht — kurzer Stream bis 23 Uhr. 🟡', 8, 6, h);
    }
    // Nach 23 Uhr: schlafen
    return make(date, shift, 'discouraged', null,
      'Nach 23 Uhr — besser schlafen. 🟠', 8, 6, h);
  }

  // ── Kein Schichteintrag → "Abend DAVOR"-Regeln anhand morgen ────────────────
  if (!shift) {
    // Morgen Tagschicht oder FAKT-Früh
    if (nextShift?.type === 'tag' || nextShift?.type === 'fakt_frueh') {
      if (h >= 22) {
        return make(date, null, 'discouraged', null,
          `${nextShift.label} morgen um ${nextShift.startTime} — jetzt schlafen. 🟠`,
          8, 8, h);
      }
      if (h >= 17) {
        return make(date, null, 'conditional', w('17:00', '22:00'),
          `Tagschicht morgen um ${nextShift.startTime} — Stream bis 22 Uhr ok, dann schlafen. 🟡`,
          8, 8, h);
      }
      // Tagsüber: unkritisch, Stream möglich
      return make(date, null, 'conditional', w('10:00', '22:00'),
        `${nextShift.label} morgen — tagsüber Stream möglich, ab 22 Uhr schlafen. 🟡`,
        8, 8, h);
    }

    // Morgen Nachtschicht
    if (nextShift?.type === 'nacht') {
      if (h >= 22) {
        return make(date, null, 'discouraged', null,
          `Nachtschicht morgen um ${nextShift.startTime} — jetzt schlafen. 🟠`,
          8, 8, h);
      }
      if (h >= 17) {
        return make(date, null, 'conditional', w('17:00', '22:00'),
          `Nachtschicht morgen — Abend noch Stream möglich bis 22 Uhr. 🟡`,
          8, 8, h);
      }
      return make(date, null, 'conditional', w('10:00', '22:00'),
        `Nachtschicht morgen — heute tagsüber kein Problem. 🟡`,
        8, 8, h);
    }

    // Morgen FAKT-Spät
    if (nextShift?.type === 'fakt_spaet') {
      if (h >= 22) {
        return make(date, null, 'discouraged', null,
          `${nextShift.label} morgen — jetzt schlafen. 🟠`,
          8, 6, h);
      }
      return make(date, null, 'conditional', w('10:00', '23:00'),
        `${nextShift.label} morgen ab ${nextShift.startTime} — heute Stream möglich. 🟡`,
        8, 6, h);
    }

    // Kein Kontext bekannt
    return make(date, null, 'conditional', w('10:00', '02:00'),
      'Kein Schichteintrag — für eine genaue Empfehlung bitte Schicht eintragen. 🟡',
      8, 8, h);
  }

  // Fallback (custom shift o.ä.)
  return make(date, shift, 'conditional', w('10:00', '23:00'),
    'Schicht bekannt — bedingt möglich. 🟡', 8, 8, h);
}

// ── Öffentliche API (mit DB-Zugriff) ─────────────────────────────────────────

export function getAvailability(date: string, currentHour?: number): AvailabilityResult {
  const hour = currentHour ?? new Date().getHours();
  const shift    = getShiftByDate(date);
  const prevShift = getShiftByDate(addDays(date, -1));
  const nextShift = getShiftByDate(addDays(date, 1));
  return computeAvailability(date, shift, prevShift, nextShift, hour);
}
