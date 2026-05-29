import { addDays, type JarvisShift, type ShiftType } from "../types/shift.types.js";
import { getShiftByDate } from "./shift-store.js";

export type StreamingQuality = "good" | "limited" | "poor";
export type StreamingRecommendation = "yes" | "conditional" | "no" | "unknown";

export type TimeWindow = {
    start: string;
    end: string;
    label: string;
    quality: StreamingQuality;
};

export type StreamingAdvice = {
    date: string;
    shift: JarvisShift | null;
    previousShift: JarvisShift | null;
    nextShift: JarvisShift | null;
    recommendation: StreamingRecommendation;
    score: number;
    timeWindows: TimeWindow[];
    reasons: string[];
    warnings: string[];
    recoveryNeeded: boolean;
    latestStreamEnd: string | null;
};

// ── Helpers ────────────────────────────────────────────────────────────────

function toMin(time: string): number {
    const [h, m] = time.split(":").map(Number);
    return h * 60 + m;
}

function fromMin(minutes: number): string {
    const c = Math.max(0, Math.min(1439, minutes));
    return `${String(Math.floor(c / 60)).padStart(2, "0")}:${String(c % 60).padStart(2, "0")}`;
}

// Wie viele Stunden Schlaf braucht man vor dieser Schicht mindestens?
const MIN_SLEEP: Record<ShiftType, number> = {
    tag: 7.5,
    nacht: 8,
    frei: 0,
    fakt_frueh: 7.5,
    fakt_spaet: 6,
    custom: 7,
};

// Wann muss man vor Schichtbeginn aufstehen? (Minuten Puffer)
const WAKEUP_BUFFER_MIN = 75;

// ── Kern-Logik ─────────────────────────────────────────────────────────────

export function getStreamingAdvice(date: string): StreamingAdvice {
    const shift = getShiftByDate(date);
    const prevDate = addDays(date, -1);
    const nextDate = addDays(date, 1);
    const previousShift = getShiftByDate(prevDate);
    const nextShift = getShiftByDate(nextDate);

    const reasons: string[] = [];
    const warnings: string[] = [];
    const timeWindows: TimeWindow[] = [];
    let score = 80;
    let recoveryNeeded = false;
    let latestStreamEnd: string | null = null;

    // ── Recovery nach Nachtschicht ───────────────────────────────────────────
    // Nachtschicht startete gestern, endet heute (overnight) → Recovery-Tag
    const isRecovery =
        previousShift?.type === "nacht" && previousShift.overnight && previousShift.endDate === date;

    if (isRecovery) {
        recoveryNeeded = true;
        score -= 40;
        reasons.push(
            `Gestern Nachtschicht (${previousShift!.startTime}–${previousShift!.endTime}+1). Dein Körper braucht Erholung.`
        );
        warnings.push("Mindestens 8h Schlaf nach Nachtschicht. Stream frühestens ab 15:00 empfohlen.");
        timeWindows.push({ start: "00:00", end: "14:59", label: "Schlaf / Erholung", quality: "poor" });
        timeWindows.push({ start: "15:00", end: "22:00", label: "Eingeschränkt möglich", quality: "limited" });
        latestStreamEnd = "22:00";
    }

    // ── Frei (und kein Recovery) ─────────────────────────────────────────────
    else if (shift?.type === "frei") {
        score += 10;
        reasons.push("Freier Tag – keine Schicht.");

        if (nextShift && nextShift.type !== "frei") {
            const wakeupMin = toMin(nextShift.startTime) - WAKEUP_BUFFER_MIN;
            const streamEndMin = wakeupMin - MIN_SLEEP[nextShift.type] * 60 - 30;
            latestStreamEnd = fromMin(streamEndMin);
            score -= 15;
            reasons.push(`Morgen: ${nextShift.label} ab ${nextShift.startTime}.`);
            warnings.push(`Spätestes Stream-Ende heute: ${latestStreamEnd} (${MIN_SLEEP[nextShift.type]}h Schlaf + Puffer).`);
            timeWindows.push({ start: "10:00", end: latestStreamEnd, label: "Freies Hauptfenster", quality: "good" });
            timeWindows.push({ start: latestStreamEnd, end: "23:59", label: "Nicht empfohlen (Schlaf für morgen)", quality: "poor" });
        } else {
            latestStreamEnd = "02:00";
            reasons.push("Morgen auch frei oder keine Schicht eingetragen.");
            timeWindows.push({ start: "10:00", end: "02:00", label: "Kein Zeitlimit", quality: "good" });
        }
    }

    // ── Nachtschicht heute (Schicht beginnt abends, endet morgen früh) ────────
    else if (shift?.type === "nacht" && !recoveryNeeded) {
        score -= 75;
        reasons.push(`Heute Nachtschicht: ${shift.startTime}–${shift.endTime} (bis morgen ${shift.endTime}).`);
        warnings.push("Du arbeitest heute Nacht. Kein langer Stream empfohlen.");

        const shiftStartMin = toMin(shift.startTime);
        const freeUntilMin = shiftStartMin - 90; // 90 Min Vorbereitung
        if (freeUntilMin > toMin("10:00")) {
            latestStreamEnd = fromMin(freeUntilMin);
            timeWindows.push({ start: "10:00", end: latestStreamEnd, label: "Nur vor der Schicht möglich", quality: "limited" });
            timeWindows.push({ start: latestStreamEnd, end: "23:59", label: "Nicht empfohlen (Nachtschicht)", quality: "poor" });
        } else {
            timeWindows.push({ start: "00:00", end: "23:59", label: "Nicht empfohlen (Nachtschicht heute)", quality: "poor" });
        }
    }

    // ── Tagschicht / FAKT Früh / FAKT Spät heute ────────────────────────────
    else if (shift && shift.type !== "frei" && !recoveryNeeded) {
        const afterShiftMin = toMin(shift.endTime) + 30;
        const afterShift = fromMin(afterShiftMin);
        reasons.push(`Heute: ${shift.label} (${shift.startTime}–${shift.endTime}). Frei ab ca. ${afterShift}.`);

        if (nextShift && nextShift.type !== "frei") {
            const wakeupMin = toMin(nextShift.startTime) - WAKEUP_BUFFER_MIN;
            const streamEndMin = wakeupMin - MIN_SLEEP[nextShift.type] * 60 - 30;
            latestStreamEnd = fromMin(streamEndMin);
            score -= 10;
            warnings.push(`Morgen: ${nextShift.label} ab ${nextShift.startTime}. Spätestes Stream-Ende: ${latestStreamEnd}.`);
            timeWindows.push({ start: afterShift, end: latestStreamEnd, label: "Fenster nach Schicht", quality: "good" });
            timeWindows.push({ start: latestStreamEnd, end: "23:59", label: "Riskant (Schlaf für morgen)", quality: "poor" });
        } else {
            latestStreamEnd = "01:00";
            timeWindows.push({ start: afterShift, end: latestStreamEnd, label: "Fenster nach Schicht", quality: "good" });
        }
    }

    // ── Keine Schicht eingetragen ────────────────────────────────────────────
    else if (!shift && !recoveryNeeded) {
        score = 50;
        reasons.push("Keine Schicht für diesen Tag eingetragen.");
        warnings.push("Für eine genaue Empfehlung bitte Schicht eintragen: 'Jarvis, morgen habe ich Tagschicht'.");
        timeWindows.push({ start: "10:00", end: "23:00", label: "Schätzung (unbekannte Schicht)", quality: "limited" });
        latestStreamEnd = "23:00";
    }

    // ── Score → Empfehlung ───────────────────────────────────────────────────
    const finalScore = Math.max(0, Math.min(100, score));
    let recommendation: StreamingRecommendation;

    if (!shift && !recoveryNeeded) {
        recommendation = "unknown";
    } else if (finalScore >= 70) {
        recommendation = "yes";
    } else if (finalScore >= 35) {
        recommendation = "conditional";
    } else {
        recommendation = "no";
    }

    return {
        date, shift, previousShift, nextShift,
        recommendation, score: finalScore,
        timeWindows, reasons, warnings,
        recoveryNeeded, latestStreamEnd,
    };
}
