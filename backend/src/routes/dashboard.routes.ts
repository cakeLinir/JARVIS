import type { FastifyInstance } from "fastify";
import { config, getConfigStatus } from "../config/config.js";
import {
  createDashboardSessionCookie,
  dashboardSessionClearCookieHeader,
  dashboardSessionSetCookieHeader,
  isDashboardRequestAuthorized,
  requireDashboardAuth,
  requireDashboardWebAuth
} from "../security/auth.js";
import {
  getAgentRuntimeStatus,
  getAgentStatus,
  getMorningLog
} from "../services/agent-state.js";
import { getCommandCounts, getRecentCommands } from "../services/command-store.js";
import { appendAuditEvent, getRecentAuditEvents } from "../services/audit-log.js";
import { getNewsSources } from "../services/news.service.js";

function numberFromEnv(value: string | undefined, fallback: number): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function runtimeOptions() {
  return {
    staleAfterSeconds: numberFromEnv(process.env.JARVIS_AGENT_STALE_AFTER_SECONDS, 45),
    offlineAfterSeconds: numberFromEnv(process.env.JARVIS_AGENT_OFFLINE_AFTER_SECONDS, 180)
  };
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function loginHtml(errorMessage = "") {
  return `<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>JARVIS Dashboard Login</title>
  <style>
    :root { color-scheme: dark; font-family: Segoe UI, system-ui, sans-serif; }
    body { margin: 0; min-height: 100vh; display: grid; place-items: center; background: #0d1117; color: #e6edf3; }
    main { width: min(460px, calc(100vw - 32px)); border: 1px solid #30363d; border-radius: 16px; padding: 24px; background: #161b22; }
    input, button { width: 100%; box-sizing: border-box; padding: 12px; border-radius: 8px; border: 1px solid #30363d; background: #0d1117; color: #e6edf3; margin-top: 12px; }
    button { cursor: pointer; background: #238636; border-color: #238636; font-weight: 700; }
    .error { color: #ff7b72; margin-top: 12px; }
    .muted { color: #8b949e; }
  </style>
</head>
<body>
  <main>
    <h1>JARVIS Dashboard</h1>
    <p class="muted">Authentifizierung erforderlich.</p>
    <input id="token" type="password" autocomplete="current-password" placeholder="Dashboard Token" autofocus />
    <button onclick="login()">Einloggen</button>
    <p id="error" class="error">${escapeHtml(errorMessage)}</p>
  </main>
<script>
async function login() {
  const token = document.getElementById('token').value.trim();
  const error = document.getElementById('error');
  error.textContent = '';

  const res = await fetch('/dashboard/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
    credentials: 'same-origin',
    body: JSON.stringify({ token })
  });

  if (res.ok) {
    window.location.href = '/dashboard';
    return;
  }

  let message = 'Login fehlgeschlagen.';
  try {
    const data = await res.json();
    message = data.message || data.error || message;
  } catch {}
  error.textContent = message;
}

document.getElementById('token').addEventListener('keydown', event => {
  if (event.key === 'Enter') {
    login();
  }
});
</script>
</body>
</html>`;
}

function dashboardHtml() {
  return `<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>JARVIS Dashboard</title>
  <style>
    :root { color-scheme: dark; font-family: Segoe UI, system-ui, sans-serif; }
    body { margin: 0; background: #0d1117; color: #e6edf3; }
    header { padding: 24px; border-bottom: 1px solid #30363d; background: #161b22; }
    main { display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); padding: 24px; }
    section { border: 1px solid #30363d; border-radius: 12px; padding: 16px; background: #161b22; }
    input, button { padding: 10px 12px; border-radius: 8px; border: 1px solid #30363d; background: #0d1117; color: #e6edf3; }
    button { cursor: pointer; background: #238636; border-color: #238636; font-weight: 600; }
    button.secondary { background: #21262d; border-color: #30363d; }
    pre { white-space: pre-wrap; overflow-wrap: anywhere; background: #0d1117; padding: 12px; border-radius: 8px; border: 1px solid #30363d; }
    .row { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
    .muted { color: #8b949e; }
  </style>
</head>
<body>
  <header>
    <h1>JARVIS Dashboard</h1>
    <p class="muted">MVP-Verwaltung für Backend, Bot, lokalen Agent, TODOs, Runtime und Realtime-Voice.</p>
    <div class="row">
      <button onclick="loadOverview()">Status laden</button>
      <button onclick="startMorning()">Morgenroutine starten</button>
      <button class="secondary" onclick="logout()">Logout</button>
    </div>
    <p class="muted">Public URL: ${escapeHtml(config.publicBaseUrl)}</p>
  </header>
  <main>
    <section><h2>Übersicht</h2><pre id="overview">Noch nicht geladen.</pre></section>
    <section><h2>Runtime</h2><pre id="runtime">Noch nicht geladen.</pre></section>
    <section><h2>Agent</h2><pre id="agent">Noch nicht geladen.</pre></section>
    <section><h2>TODO</h2><pre id="todo">Noch nicht geladen.</pre></section>
    <section><h2>Morning Log</h2><pre id="morning">Noch nicht geladen.</pre></section>
    <section><h2>Konfiguration</h2><pre id="configuration">Noch nicht geladen.</pre></section>
    <section><h2>Commands</h2><pre id="commands">Noch nicht geladen.</pre></section>
    <section><h2>Audit</h2><pre id="audit">Noch nicht geladen.</pre></section>
  </main>
<script>
function pretty(value) { return JSON.stringify(value, null, 2); }
async function fetchJson(url, options = {}) {
  const res = await fetch(url, { ...options, credentials: 'same-origin' });
  if (res.status === 401 || res.status === 403) {
    window.location.href = '/dashboard/login';
    return null;
  }
  return await res.json();
}
async function loadOverview() {
  const data = await fetchJson('/api/dashboard/overview', { headers: { 'Accept': 'application/json' } });
  if (!data) return;
  document.getElementById('overview').textContent = pretty(data.overview ?? data);
  document.getElementById('runtime').textContent = pretty(data.runtime ?? null);
  document.getElementById('agent').textContent = pretty(data.agentStatus ?? null);
  document.getElementById('todo').textContent = pretty(data.todo ?? null);
  document.getElementById('morning').textContent = pretty(data.morningLog ?? null);
  document.getElementById('configuration').textContent = pretty(data.configuration ?? null);
  document.getElementById('commands').textContent = pretty(data.recentCommands ?? []);
  document.getElementById('audit').textContent = pretty(data.recentAuditEvents ?? []);
}
async function startMorning() {
  const data = await fetchJson('/api/dashboard/commands/morning-routine', {
    method: 'POST',
    headers: { 'Accept': 'application/json', 'Content-Type': 'application/json' },
    body: JSON.stringify({ confirm: 'START' })
  });
  if (!data) return;
  alert(pretty(data));
  await loadOverview();
}
async function logout() {
  await fetch('/dashboard/logout', { method: 'POST', credentials: 'same-origin' });
  window.location.href = '/dashboard/login';
}
loadOverview();
</script>
</body>
</html>`;
}

function buildTodoOverview() {
  const morningLog = getMorningLog();

  if (!morningLog) {
    return {
      status: "unknown",
      message: "Noch kein Morning-Log vorhanden. Starte den Agent oder die Morgenroutine.",
      provider: null,
      openItems: []
    };
  }

  return {
    status: "ready",
    provider: morningLog.todoProvider ?? morningLog.todoStatus?.provider ?? "unknown",
    total: morningLog.todoStatus?.total ?? null,
    open: morningLog.todoStatus?.open ?? morningLog.todos.length,
    dueTodayOrUnscheduled: morningLog.todoStatus?.dueTodayOrUnscheduled ?? morningLog.todos.length,
    items: morningLog.todoStatus?.items ?? morningLog.todos,
    lastUpdatedAt: morningLog.receivedAt
  };
}

function isTokenBody(body: unknown): body is { token: string } {
  return (
    typeof body === "object" &&
    body !== null &&
    "token" in body &&
    typeof (body as { token: unknown }).token === "string"
  );
}

export async function dashboardRoutes(server: FastifyInstance) {
  server.get("/dashboard/login", async (request, reply) => {
    if (isDashboardRequestAuthorized(request)) {
      return reply.redirect("/dashboard", 303);
    }

    return reply.type("text/html; charset=utf-8").send(loginHtml());
  });

  server.post("/dashboard/login", async (request, reply) => {
    const body = request.body;

    if (!isTokenBody(body) || body.token !== config.dashboardToken) {
      request.log.warn("Dashboard login failed");
      return reply.code(403).send({
        ok: false,
        error: "invalid_dashboard_token",
        message: "Dashboard Token ungültig."
      });
    }

    const session = createDashboardSessionCookie();

    reply.header(
      "Set-Cookie",
      dashboardSessionSetCookieHeader(session)
    );

    request.log.info("Dashboard login successful");

    return {
      ok: true
    };
  });

  server.post("/dashboard/logout", async (_request, reply) => {
    reply.header("Set-Cookie", dashboardSessionClearCookieHeader());

    return {
      ok: true
    };
  });

  server.get(
    "/dashboard",
    {
      preHandler: requireDashboardWebAuth
    },
    async (_request, reply) => {
      return reply.type("text/html; charset=utf-8").send(dashboardHtml());
    }
  );

  server.get(
    "/api/dashboard/overview",
    {
      preHandler: requireDashboardAuth
    },
    async () => {
      const configuration = getConfigStatus();
      const todo = buildTodoOverview();
      const runtime = getAgentRuntimeStatus(runtimeOptions());

      return {
        ok: true,
        overview: {
          service: "jarvis-backend",
          now: new Date().toISOString(),
          runtimeState: runtime.state,
          publicBaseUrl: config.publicBaseUrl,
          realtimeModel: config.realtimeModel,
          realtimeVoice: config.realtimeVoice,
          newsSources: getNewsSources().map(source => source.name),
          commandCounts: getCommandCounts(),
          configurationSummary: configuration.summary,
          todoProvider: todo.provider,
          todoOpen: todo.open
        },
        runtime,
        configuration,
        todo,
        agentStatus: getAgentStatus(),
        morningLog: getMorningLog(),
        recentCommands: getRecentCommands(10),
        recentAuditEvents: getRecentAuditEvents(20)
      };
    }
  );

  server.post(
    "/api/dashboard/commands/morning-routine",
    {
      preHandler: requireDashboardAuth
    },
    async (request, reply) => {
      const body = request.body as { confirm?: string } | undefined;

      if (body?.confirm !== "START") {
        return reply.code(400).send({
          ok: false,
          error: "confirmation_required",
          message: "Zum Start muss confirm exakt START sein."
        });
      }

      const { addCommand, createCommandId, createCorrelationId } = await import("../services/command-store.js");
      const command = addCommand({
        id: createCommandId(),
        correlationId: createCorrelationId(),
        type: "morning_routine",
        status: "pending",
        requestedBy: "dashboard",
        source: "dashboard",
        discordRoleIds: [],
        payload: {
          source: "dashboard"
        },
        createdAt: new Date().toISOString()
      });

      appendAuditEvent({
        component: "backend",
        action: "command.create",
        result: "accepted",
        commandId: command.id,
        correlationId: command.correlationId,
        actor: {
          type: "dashboard",
          id: "dashboard"
        },
        message: "Dashboard hat Morning-Routine-Command erstellt.",
        details: {
          type: command.type,
          source: command.source,
          requestedBy: command.requestedBy
        }
      });

      return {
        ok: true,
        command
      };
    }
  );
}
