import fs from "node:fs";
import path from "node:path";
import { appendAuditEvent } from "./audit-log.js";
import {
    addDays,
    createShiftId,
    SHIFT_DEFINITIONS,
    type JarvisShift,
    type ShiftSource,
    type ShiftType,
} from "../types/shift.types.js";

const dataDir = path.resolve(process.cwd(), ".runtime", "data");
const storePath = path.join(dataDir, "shifts.json");

let shifts: JarvisShift[] = [];

// ── Persistenz ─────────────────────────────────────────────────────────────

function ensureStoreExists(): void {
    if (!fs.existsSync(dataDir)) fs.mkdirSync(dataDir, { recursive: true });
    if (!fs.existsSync(storePath)) {
        fs.writeFileSync(storePath, JSON.stringify({ version: 1, shifts: [] }, null, 2), "utf-8");
    }
}

export function saveShifts(): void {
    ensureStoreExists();
    const tmp = `${storePath}.tmp`;
    fs.writeFileSync(tmp, JSON.stringify({ version: 1, shifts }, null, 2), "utf-8");
    fs.renameSync(tmp, storePath);
}

export function loadShifts(): void {
    ensureStoreExists();
    try {
        const raw = fs.readFileSync(storePath, "utf-8");
        const parsed = JSON.parse(raw);
        shifts = Array.isArray(parsed) ? parsed : (parsed?.shifts ?? []);
    } catch {
        const backup = `${storePath}.broken-${Date.now()}.bak`;
        if (fs.existsSync(storePath)) fs.copyFileSync(storePath, backup);
        shifts = [];
        saveShifts();
    }
}

// ── Helpers ────────────────────────────────────────────────────────────────

export function getTodayDateStr(): string {
    return new Date().toISOString().slice(0, 10);
}

export function getTomorrowDateStr(): string {
    return addDays(getTodayDateStr(), 1);
}

function buildShiftObject(
    existingId: string | null,
    existingCreatedAt: string | null,
    date: string,
    type: ShiftType,
    source: ShiftSource,
    notes?: string
): JarvisShift {
    if (type === "custom") throw new Error("custom shifts bitte manuell über PUT aufbauen.");
    const def = SHIFT_DEFINITIONS[type];
    const now = new Date().toISOString();
    return {
        id: existingId ?? createShiftId(),
        date,
        type,
        startTime: def.startTime,
        endTime: def.endTime,
        overnight: def.overnight,
        endDate: def.overnight ? addDays(date, 1) : undefined,
        label: def.label,
        source,
        notes,
        createdAt: existingCreatedAt ?? now,
        updatedAt: now,
    };
}

// ── UPSERT — nur eine Schicht pro Datum ────────────────────────────────────

export function upsertShift(
    date: string, type: ShiftType, source: ShiftSource, notes?: string
): JarvisShift {
    const existingIdx = shifts.findIndex(s => s.date === date);
    const existing = existingIdx >= 0 ? shifts[existingIdx] : null;

    const shift = buildShiftObject(
        existing?.id ?? null,
        existing?.createdAt ?? null,
        date, type, source, notes
    );

    if (existing) {
        shifts[existingIdx] = shift;
        appendAuditEvent({
            component: "shift-store", action: "shift.update", result: "completed",
            message: `Schicht geändert: ${date} → ${shift.label}`,
            details: { id: shift.id, date, type, previousType: existing.type }
        });
    } else {
        shifts.push(shift);
        appendAuditEvent({
            component: "shift-store", action: "shift.create", result: "completed",
            message: `Schicht eingetragen: ${date} → ${shift.label}`,
            details: { id: shift.id, date, type }
        });
    }

    saveShifts();
    return shift;
}

// ── Read ───────────────────────────────────────────────────────────────────

export function getShiftByDate(date: string): JarvisShift | null {
    return shifts.find(s => s.date === date) ?? null;
}

export function getShiftById(id: string): JarvisShift | null {
    return shifts.find(s => s.id === id) ?? null;
}

export function getShiftsInRange(from: string, to: string): JarvisShift[] {
    return shifts
        .filter(s => s.date >= from && s.date <= to)
        .sort((a, b) => a.date.localeCompare(b.date));
}

// ── Delete ─────────────────────────────────────────────────────────────────

export function deleteShift(id: string): boolean {
    const idx = shifts.findIndex(s => s.id === id);
    if (idx < 0) return false;
    const [removed] = shifts.splice(idx, 1);
    saveShifts();
    appendAuditEvent({
        component: "shift-store", action: "shift.delete", result: "completed",
        message: `Schicht gelöscht: ${removed.date} ${removed.label}`,
        details: { id: removed.id }
    });
    return true;
}
