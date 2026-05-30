import { useCallback, useEffect, useMemo, useState } from "react";
import { getDashboardOverview, logoutDashboard, startMorningRoutine } from "../api/client";
import { AvailabilityWidget } from "../components/AvailabilityWidget";
import { DataTable } from "../components/DataTable";
import { JsonDetails } from "../components/JsonDetails";
import { KeyValueList } from "../components/KeyValueList";
import { MetricCard } from "../components/MetricCard";
import { Panel } from "../components/Panel";
import { StatusBadge } from "../components/StatusBadge";
import type { AuditItem, CommandItem, ConfigCheck, DashboardOverviewResponse, TodoItem } from "../types/dashboard";

type Props = {
  onAuthRequired: () => void;
};

function formatDate(value?: string | null) {
  if (!value) {
    return "—";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return parsed.toLocaleString("de-DE");
}

function todoTitle(item: TodoItem | string) {
  return typeof item === "string" ? item : item.title ?? "—";
}

function todoStatus(item: TodoItem | string) {
  return typeof item === "string" ? "open" : item.status ?? "open";
}

function todoDueDate(item: TodoItem | string) {
  return typeof item === "string" ? "—" : item.dueDate ?? "—";
}

export function DashboardPage({ onAuthRequired }: Props) {
  const [data, setData] = useState<DashboardOverviewResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await getDashboardOverview();
      setData(response);
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : String(caught);
      if (message === "AUTH_REQUIRED") {
        onAuthRequired();
        return;
      }
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [onAuthRequired]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!autoRefresh) {
      return;
    }

    const timer = window.setInterval(() => {
      void load();
    }, 30_000);

    return () => window.clearInterval(timer);
  }, [autoRefresh, load]);

  const todoItems = useMemo(() => data?.todo?.items ?? [], [data]);
  const configChecks = useMemo(() => data?.configuration?.checks ?? [], [data]);
  const commands = useMemo(() => data?.recentCommands ?? [], [data]);
  const auditEvents = useMemo(() => data?.recentAuditEvents ?? [], [data]);

  async function handleMorningRoutine() {
    try {
      await startMorningRoutine();
      await load();
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : String(caught);
      if (message === "AUTH_REQUIRED") {
        onAuthRequired();
        return;
      }
      setError(message);
    }
  }

  async function handleLogout() {
    await logoutDashboard();
    onAuthRequired();
  }

  return (
    <>
      <header className="app-header">
        <div>
          <h1>JARVIS Dashboard</h1>
          <p className="muted">
            Backend, Agent, TODOs, Commands, Audit und Runtime in einer getrennten Frontend-App.
          </p>
          <p className="muted">Public URL: {data?.overview?.publicBaseUrl ?? "—"}</p>
        </div>
        <div className="header-actions">
          <button onClick={() => void load()} disabled={loading}>
            {loading ? "Lädt..." : "Status laden"}
          </button>
          <button onClick={() => void handleMorningRoutine()}>Morgenroutine starten</button>
          <button className="secondary" onClick={() => setAutoRefresh(value => !value)}>
            Auto-Refresh: {autoRefresh ? "30s" : "aus"}
          </button>
          <button className="secondary" onClick={() => void handleLogout()}>
            Logout
          </button>
        </div>
      </header>

      <main className="dashboard-shell">
        {error ? <div className="error-box">Fehler: {error}</div> : null}

        {/* Metriken-Übersicht */}
        <div className="metric-grid">
          <MetricCard label="Runtime" value={<StatusBadge value={data?.runtime?.state ?? "unknown"} />} />
          <MetricCard
            label="TODOs offen"
            value={data?.todoStats?.open ?? data?.todo?.open ?? "—"}
            hint={data?.todoStats ? `${data.todoStats.dueToday} heute, ${data.todoStats.overdue} überfällig` : (data?.todo?.provider ?? undefined)}
          />
          <MetricCard
            label="Config fehlend"
            value={data?.configuration?.summary?.missingRequired ?? "—"}
            hint={`${data?.configuration?.summary?.total ?? 0} Checks`}
          />
          <MetricCard
            label="Session"
            value={`${Math.round((data?.dashboardSession?.idleTimeoutSeconds ?? 1800) / 60)} min`}
            hint={data?.dashboardSession?.mode ?? "server"}
          />
        </div>

        {/* TODO-Statistiken (Live aus SQLite) */}
        {data?.todoStats && (
          <div className="todo-stats-grid">
            <div className="todo-stat-card">
              <div className="todo-stat-value" style={{ color: "var(--text)" }}>
                {data.todoStats.open}
              </div>
              <div className="todo-stat-label">Offen gesamt</div>
            </div>
            <div className="todo-stat-card">
              <div
                className="todo-stat-value"
                style={{ color: data.todoStats.dueToday > 0 ? "var(--warn)" : "var(--ok)" }}
              >
                {data.todoStats.dueToday}
              </div>
              <div className="todo-stat-label">Heute fällig</div>
            </div>
            <div className="todo-stat-card">
              <div
                className="todo-stat-value"
                style={{ color: data.todoStats.overdue > 0 ? "var(--bad)" : "var(--ok)" }}
              >
                {data.todoStats.overdue}
              </div>
              <div className="todo-stat-label">Überfällig</div>
            </div>
          </div>
        )}

        <div className="panel-grid">
          {/* Streaming-Verfügbarkeit für heute und morgen */}
          {(data?.streamToday || data?.streamTomorrow) && (
            <Panel title="Streaming-Verfügbarkeit">
              <AvailabilityWidget today={data.streamToday} tomorrow={data.streamTomorrow} />
            </Panel>
          )}

          <Panel title="Runtime">
            <KeyValueList
              items={[
                { label: "Status", value: <StatusBadge value={data?.runtime?.state ?? "unknown"} /> },
                { label: "Letzter Status", value: data?.runtime?.lastStatus ?? "—" },
                { label: "Alter", value: data?.runtime?.ageSeconds ?? "—" },
                { label: "Zuletzt empfangen", value: formatDate(data?.runtime?.lastReceivedAt) },
                { label: "Stale nach", value: `${data?.runtime?.staleAfterSeconds ?? "—"}s` },
                { label: "Offline nach", value: `${data?.runtime?.offlineAfterSeconds ?? "—"}s` }
              ]}
            />
          </Panel>

          <Panel title="Agent">
            <KeyValueList
              items={[
                { label: "Agent", value: data?.agentStatus?.agentName ?? "—" },
                { label: "Host", value: data?.agentStatus?.hostname ?? "—" },
                { label: "Status", value: <StatusBadge value={data?.agentStatus?.status ?? "unknown"} /> },
                { label: "Agent-Zeit", value: formatDate(data?.agentStatus?.timestamp) },
                { label: "Backend empfangen", value: formatDate(data?.agentStatus?.receivedAt) }
              ]}
            />
          </Panel>

          <Panel title="TODO">
            <KeyValueList
              items={[
                { label: "Status", value: <StatusBadge value={data?.todo?.status ?? "unknown"} /> },
                { label: "Provider", value: data?.todo?.provider ?? "—" },
                { label: "Gesamt", value: data?.todo?.total ?? "—" },
                { label: "Offen", value: data?.todo?.open ?? "—" },
                { label: "Heute/ohne Datum", value: data?.todo?.dueTodayOrUnscheduled ?? "—" }
              ]}
            />
            <DataTable<TodoItem | string>
              rows={todoItems.slice(0, 12)}
              columns={[
                { key: "title", label: "Titel", render: todoTitle },
                { key: "status", label: "Status", render: row => <StatusBadge value={todoStatus(row)} /> },
                { key: "dueDate", label: "Fällig", render: todoDueDate }
              ]}
              emptyText="Keine TODOs im letzten Agent-Status."
            />
          </Panel>

          <Panel title="Konfiguration">
            <DataTable<ConfigCheck>
              rows={configChecks}
              columns={[
                { key: "key", label: "Key", render: row => row.key },
                { key: "configured", label: "Status", render: row => <StatusBadge value={row.configured ? "ok" : row.required ? "missing" : "optional"} /> },
                { key: "message", label: "Hinweis", render: row => row.message }
              ]}
            />
          </Panel>

          <Panel title="Commands">
            <DataTable<CommandItem>
              rows={commands}
              columns={[
                { key: "createdAt", label: "Zeit", render: row => formatDate(row.createdAt) },
                { key: "type", label: "Typ", render: row => row.type ?? "—" },
                { key: "status", label: "Status", render: row => <StatusBadge value={row.status ?? "unknown"} /> },
                { key: "requestedBy", label: "Von", render: row => row.requestedBy ?? "—" }
              ]}
            />
          </Panel>

          <Panel title="Audit">
            <DataTable<AuditItem>
              rows={auditEvents}
              columns={[
                { key: "timestamp", label: "Zeit", render: row => formatDate(row.timestamp) },
                { key: "component", label: "Komponente", render: row => row.component ?? "—" },
                { key: "action", label: "Aktion", render: row => row.action ?? "—" },
                { key: "result", label: "Resultat", render: row => <StatusBadge value={row.result ?? "unknown"} /> },
                { key: "message", label: "Nachricht", render: row => row.message ?? "—" }
              ]}
            />
          </Panel>

          <Panel title="Morning Log">
            <KeyValueList
              items={[
                { label: "Empfangen", value: formatDate(data?.morningLog?.receivedAt) },
                { label: "Agent-Zeit", value: formatDate(data?.morningLog?.timestamp) },
                { label: "TODO Provider", value: data?.morningLog?.todoProvider ?? "—" },
                { label: "Projektstatus", value: data?.morningLog?.projectSummary ?? "—" }
              ]}
            />
          </Panel>
        </div>

        <JsonDetails data={data} />
      </main>
    </>
  );
}
