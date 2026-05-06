import type { FastifyInstance } from "fastify";
import { config } from "../config/config.js";
import { requireAnyJarvisAuth, requireDashboardAuth } from "../security/auth.js";
import { getAgentStatus, getMorningLog } from "../services/agent-state.js";
import { getCommandCounts, getRecentCommands } from "../services/command-store.js";
import { getNewsSources } from "../services/news.service.js";

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
    pre { white-space: pre-wrap; overflow-wrap: anywhere; background: #0d1117; padding: 12px; border-radius: 8px; border: 1px solid #30363d; }
    .row { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
    .muted { color: #8b949e; }
  </style>
</head>
<body>
  <header>
    <h1>JARVIS Dashboard</h1>
    <p class="muted">MVP-Verwaltung für Backend, Bot, lokalen Agent und Realtime-Voice.</p>
    <div class="row">
      <input id="token" type="password" placeholder="Dashboard Token" size="42" />
      <button onclick="loadOverview()">Status laden</button>
      <button onclick="startMorning()">Morgenroutine starten</button>
    </div>
  </header>
  <main>
    <section><h2>Übersicht</h2><pre id="overview">Noch nicht geladen.</pre></section>
    <section><h2>Agent</h2><pre id="agent">Noch nicht geladen.</pre></section>
    <section><h2>Morning Log</h2><pre id="morning">Noch nicht geladen.</pre></section>
    <section><h2>Commands</h2><pre id="commands">Noch nicht geladen.</pre></section>
  </main>
<script>
function token() { return document.getElementById('token').value.trim(); }
function headers() { return { 'Authorization': 'Bearer ' + token(), 'Accept': 'application/json', 'Content-Type': 'application/json' }; }
function pretty(value) { return JSON.stringify(value, null, 2); }
async function loadOverview() {
  const res = await fetch('/api/dashboard/overview', { headers: headers() });
  const data = await res.json();
  document.getElementById('overview').textContent = pretty(data.overview ?? data);
  document.getElementById('agent').textContent = pretty(data.agentStatus ?? null);
  document.getElementById('morning').textContent = pretty(data.morningLog ?? null);
  document.getElementById('commands').textContent = pretty(data.recentCommands ?? []);
}
async function startMorning() {
  const res = await fetch('/api/dashboard/commands/morning-routine', { method: 'POST', headers: headers(), body: JSON.stringify({ confirm: 'START' }) });
  const data = await res.json();
  alert(pretty(data));
  await loadOverview();
}
</script>
</body>
</html>`;
}

export async function dashboardRoutes(server: FastifyInstance) {
  server.get("/dashboard", async (_request, reply) => {
    return reply.type("text/html; charset=utf-8").send(dashboardHtml());
  });

  server.get(
    "/api/dashboard/overview",
    {
      preHandler: requireAnyJarvisAuth
    },
    async () => {
      return {
        ok: true,
        overview: {
          service: "jarvis-backend",
          now: new Date().toISOString(),
          realtimeModel: config.realtimeModel,
          realtimeVoice: config.realtimeVoice,
          newsSources: getNewsSources().map(source => source.name),
          commandCounts: getCommandCounts()
        },
        agentStatus: getAgentStatus(),
        morningLog: getMorningLog(),
        recentCommands: getRecentCommands(10)
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

      const { addCommand, createCommandId } = await import("../services/command-store.js");
      const command = addCommand({
        id: createCommandId(),
        type: "morning_routine",
        status: "pending",
        requestedBy: "dashboard",
        discordRoleIds: [],
        payload: {
          source: "dashboard"
        },
        createdAt: new Date().toISOString()
      });

      return {
        ok: true,
        command
      };
    }
  );
}
