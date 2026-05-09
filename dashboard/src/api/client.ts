import type { DashboardOverviewResponse } from "../types/dashboard";

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init,
    credentials: "include",
    headers: {
      Accept: "application/json",
      ...(init?.headers ?? {})
    }
  });

  if (response.status === 401 || response.status === 403) {
    throw new Error("AUTH_REQUIRED");
  }

  if (!response.ok) {
    throw new Error(`HTTP_${response.status}`);
  }

  return response.json() as Promise<T>;
}

export async function getDashboardOverview(): Promise<DashboardOverviewResponse> {
  return requestJson<DashboardOverviewResponse>("/api/dashboard/overview");
}

export async function startMorningRoutine(): Promise<unknown> {
  return requestJson<unknown>("/api/dashboard/commands/morning-routine", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ confirm: "START" })
  });
}

export async function logoutDashboard(): Promise<void> {
  await fetch("/dashboard/logout", {
    method: "POST",
    credentials: "include"
  });
}
