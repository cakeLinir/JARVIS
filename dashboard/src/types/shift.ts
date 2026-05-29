export type ShiftType = "tag" | "nacht" | "frei" | "fakt_frueh" | "fakt_spaet";
export type ShiftSource = "voice" | "dashboard" | "discord" | "manual";

export type Shift = {
    id: string;
    date: string;     // YYYY-MM-DD
    type: ShiftType;
    startTime: string;     // HH:MM
    endTime: string;     // HH:MM
    overnight: boolean;
    endDate?: string;
    label: string;
    source: ShiftSource;
    notes?: string;
    createdAt: string;
    updatedAt: string;
};

export type ShiftListResponse = {
    ok: boolean;
    count: number;
    from: string;
    to: string;
    shifts: Shift[];
};

export type ShiftResponse = {
    ok: boolean;
    shift: Shift | null;
};

export type TimeWindow = {
    start: string;
    end: string;
    label: string;
    quality: "good" | "limited" | "poor";
};

export type StreamingAdvice = {
    date: string;
    shift: Shift | null;
    previousShift: Shift | null;
    nextShift: Shift | null;
    recommendation: "yes" | "conditional" | "no" | "unknown";
    score: number;
    timeWindows: TimeWindow[];
    reasons: string[];
    warnings: string[];
    recoveryNeeded: boolean;
    latestStreamEnd: string | null;
};

export type StreamingAdviceResponse = {
    ok: boolean;
    advice: StreamingAdvice;
};

export type StreamingWeekResponse = {
    ok: boolean;
    count: number;
    advice: StreamingAdvice[];
};

export const SHIFT_TYPE_LABELS: Record<ShiftType, string> = {
    tag: "Tagschicht",
    nacht: "Nachtschicht",
    frei: "Frei",
    fakt_frueh: "FAKT Früh",
    fakt_spaet: "FAKT Spät",
};

export const SHIFT_TYPE_TIMES: Record<ShiftType, string> = {
    tag: "07:00 – 19:00",
    nacht: "19:00 – 07:00",
    frei: "Freier Tag",
    fakt_frueh: "07:00 – 14:30",
    fakt_spaet: "14:30 – 21:30",
};

// CSS-Klassen-Suffix für Shift-Farben (z.B. "shift-tag", "shift-nacht")
export const SHIFT_TYPE_CLASS: Record<ShiftType, string> = {
    tag: "shift-tag",
    nacht: "shift-nacht",
    frei: "shift-frei",
    fakt_frueh: "shift-fakt-frueh",
    fakt_spaet: "shift-fakt-spaet",
};
