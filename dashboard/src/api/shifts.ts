import type {
    ShiftListResponse,
    ShiftResponse,
    StreamingAdviceResponse,
    StreamingWeekResponse,
} from "../types/shift";

async function req<T>(url: string, init?: RequestInit): Promise<T> {
    const res = await fetch(url, {
        ...init,
        credentials: "include",
        headers: { Accept: "application/json", ...(init?.headers ?? {}) },
    });
    if (res.status === 401 || res.status === 403) throw new Error("AUTH_REQUIRED");
    if (!res.ok) throw new Error(`HTTP_${res.status}`);
    return res.json() as Promise<T>;
}

function json(body: unknown): RequestInit {
    return {
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
    };
}

export async function getShifts(from?: string, to?: string): Promise<ShiftListResponse> {
    const q = new URLSearchParams();
    if (from) q.set("from", from);
    if (to) q.set("to", to);
    const qs = q.toString() ? `?${q.toString()}` : "";
    return req<ShiftListResponse>(`/api/shifts${qs}`);
}

export async function getShiftForDate(date: string): Promise<ShiftResponse> {
    return req<ShiftResponse>(`/api/shifts/${date}`).catch(() => ({ ok: true, shift: null }));
}

export async function getTodayShift(): Promise<ShiftResponse> {
    return req<ShiftResponse>("/api/shifts/today");
}

export async function getTomorrowShift(): Promise<ShiftResponse> {
    return req<ShiftResponse>("/api/shifts/tomorrow");
}

export async function upsertShift(data: {
    date: string;
    type: string;
    notes?: string;
    source?: string;
}): Promise<ShiftResponse> {
    return req<ShiftResponse>("/api/shifts", {
        method: "POST",
        ...json({ ...data, source: data.source ?? "dashboard" }),
    });
}

export async function deleteShift(id: string): Promise<{ ok: boolean }> {
    return req<{ ok: boolean }>(`/api/shifts/${id}`, { method: "DELETE" });
}

export async function getStreamingAdviceForDate(date: string): Promise<StreamingAdviceResponse> {
    return req<StreamingAdviceResponse>(`/api/streaming/advice?date=${date}`);
}

export async function getStreamingAdviceToday(): Promise<StreamingAdviceResponse> {
    return req<StreamingAdviceResponse>("/api/streaming/advice/today");
}

export async function getStreamingAdviceTomorrow(): Promise<StreamingAdviceResponse> {
    return req<StreamingAdviceResponse>("/api/streaming/advice/tomorrow");
}

export async function getStreamingAdviceWeek(): Promise<StreamingWeekResponse> {
    return req<StreamingWeekResponse>("/api/streaming/advice/week");
}
