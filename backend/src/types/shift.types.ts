import { randomUUID } from "node:crypto";

export type ShiftType =
    | "tag"         // 07:00–19:00
    | "nacht"       // 19:00–07:00 (+1 Tag)
    | "frei"
    | "fakt_frueh"  // 07:00–14:30
    | "fakt_spaet"  // 14:30–21:30
    | "custom";

export type ShiftSource = "voice" | "dashboard" | "discord" | "manual";

export type JarvisShift = {
    id: string;
    date: string;        // YYYY-MM-DD — Kalendertag des Schichtbeginns
    type: ShiftType;
    startTime: string;   // HH:MM
    endTime: string;     // HH:MM
    overnight: boolean;  // true wenn endTime am nächsten Kalendertag liegt
    endDate?: string;    // YYYY-MM-DD — gesetzt wenn overnight=true
    label: string;
    source: ShiftSource;
    notes?: string;
    createdAt: string;
    updatedAt: string;
};

export type ShiftDefinition = {
    startTime: string;
    endTime: string;
    overnight: boolean;
    label: string;
    workHours: number;
};

export const SHIFT_DEFINITIONS: Record<Exclude<ShiftType, "custom">, ShiftDefinition> = {
    tag: { startTime: "07:00", endTime: "19:00", overnight: false, label: "Tagschicht", workHours: 12 },
    nacht: { startTime: "19:00", endTime: "07:00", overnight: true, label: "Nachtschicht", workHours: 12 },
    frei: { startTime: "00:00", endTime: "23:59", overnight: false, label: "Frei", workHours: 0 },
    fakt_frueh: { startTime: "07:00", endTime: "14:30", overnight: false, label: "FAKT IST! Früh", workHours: 7.5 },
    fakt_spaet: { startTime: "14:30", endTime: "21:30", overnight: false, label: "FAKT IST! Spät", workHours: 7 },
};

export function createShiftId(): string {
    return `shift_${Date.now()}_${randomUUID().slice(0, 8)}`;
}

export function addDays(dateStr: string, days: number): string {
    const d = new Date(`${dateStr}T00:00:00`);
    d.setDate(d.getDate() + days);
    return d.toISOString().slice(0, 10);
}
