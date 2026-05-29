import type { Todo, TodoListResponse, TodoResponse } from "../types/todo";

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

export async function getTodos(params?: {
    status?: string;
    category?: string;
    date?: string;
}): Promise<TodoListResponse> {
    const q = new URLSearchParams();
    if (params?.status) q.set("status", params.status);
    if (params?.category) q.set("category", params.category);
    if (params?.date) q.set("date", params.date);
    const qs = q.toString() ? `?${q.toString()}` : "";
    return req<TodoListResponse>(`/api/todos${qs}`);
}

export async function getDueTodayTodos(): Promise<TodoListResponse> {
    return req<TodoListResponse>("/api/todos/due-today");
}

export async function createTodo(data: {
    title: string;
    description?: string;
    priority?: number;
    category?: string;
    dueDate?: string;
    dueTime?: string;
    reminderMinutes?: number;
    source?: string;
}): Promise<TodoResponse> {
    return req<TodoResponse>("/api/todos", { method: "POST", ...json({ ...data, source: data.source ?? "dashboard" }) });
}

export async function completeTodo(id: string): Promise<TodoResponse> {
    return req<TodoResponse>(`/api/todos/${id}/complete`, { method: "POST", ...json({ actor: "dashboard" }) });
}

export async function rescheduleTodo(
    id: string, dueDate: string, dueTime?: string
): Promise<TodoResponse> {
    return req<TodoResponse>(`/api/todos/${id}/reschedule`, {
        method: "POST",
        ...json({ dueDate, dueTime, actor: "dashboard" }),
    });
}

export async function updateTodo(id: string, changes: Partial<Todo>): Promise<TodoResponse> {
    return req<TodoResponse>(`/api/todos/${id}`, {
        method: "PATCH",
        ...json({ ...changes, actor: "dashboard" }),
    });
}

export async function deleteTodo(id: string): Promise<{ ok: boolean }> {
    return req<{ ok: boolean }>(`/api/todos/${id}`, { method: "DELETE" });
}
