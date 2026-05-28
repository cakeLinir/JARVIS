import type { FastifyInstance, FastifyReply } from "fastify";
import { config, getConfigStatus, isUsableSecret } from "../config/config.js";
import {
  createDashboardOAuthState,
  createDashboardSession,
  dashboardOAuthStateClearCookieHeader,
  dashboardOAuthStateSetCookieHeader,
  dashboardSessionClearCookieHeader,
  dashboardSessionSetCookieHeader,
  destroyDashboardSession,
  getDashboardSession,
  getDashboardSessionStatus,
  requireDashboardAuth,
  requireDashboardWebAuth,
  verifyDashboardOAuthState
} from "../security/auth.js";
import {
  getAgentRuntimeStatus,
  getAgentStatus,
  getMorningLog
} from "../services/agent-state.js";
import { addCommand, createCommandId, createCorrelationId, getCommandCounts, getRecentCommands } from "../services/command-store.js";
import { appendAuditEvent, getRecentAuditEvents } from "../services/audit-log.js";
import { getNewsSources } from "../services/news.service.js";

type DiscordTokenResponse = {
  access_token: string;
  token_type: string;
  expires_in?: number;
  scope?: string;
};

type DiscordUser = {
  id: string;
  username?: string;
  global_name?: string | null;
};

type DiscordGuildMember = {
  user?: DiscordUser;
  roles?: string[];
};

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

function discordOAuthConfigured(): boolean {
  return (
    Boolean(config.discordOAuthClientId) &&
    isUsableSecret(config.discordOAuthClientSecret) &&
    Boolean(config.discordOAuthRedirectUri)
  );
}

function oauthScopes(): string[] {
  const scopes = ["identify"];

  if (config.allowedDiscordRoleIds.length > 0) {
    scopes.push("guilds.members.read");
  }

  return scopes;
}

function discordAuthorizeUrl(state: string): string {
  const url = new URL("https://discord.com/oauth2/authorize");
  url.searchParams.set("client_id", config.discordOAuthClientId);
  url.searchParams.set("response_type", "code");
  url.searchParams.set("redirect_uri", config.discordOAuthRedirectUri);
  url.searchParams.set("scope", oauthScopes().join(" "));
  url.searchParams.set("state", state);
  url.searchParams.set("prompt", "none");
  return url.toString();
}

async function exchangeDiscordCode(code: string): Promise<DiscordTokenResponse> {
  const body = new URLSearchParams();
  body.set("client_id", config.discordOAuthClientId);
  body.set("client_secret", config.discordOAuthClientSecret);
  body.set("grant_type", "authorization_code");
  body.set("code", code);
  body.set("redirect_uri", config.discordOAuthRedirectUri);

  const response = await fetch(`${config.discordApiBaseUrl}/oauth2/token`, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
      Accept: "application/json"
    },
    body
  });

  if (!response.ok) {
    const raw = await response.text();
    throw new Error(`Discord OAuth token exchange failed: HTTP ${response.status} ${raw}`);
  }

  return response.json() as Promise<DiscordTokenResponse>;
}

async function fetchDiscordUser(accessToken: string): Promise<DiscordUser> {
  const response = await fetch(`${config.discordApiBaseUrl}/users/@me`, {
    headers: {
      Authorization: `Bearer ${accessToken}`,
      Accept: "application/json"
    }
  });

  if (!response.ok) {
    const raw = await response.text();
    throw new Error(`Discord user fetch failed: HTTP ${response.status} ${raw}`);
  }

  return response.json() as Promise<DiscordUser>;
}

async function fetchDiscordGuildMember(accessToken: string): Promise<DiscordGuildMember | null> {
  if (!config.discordGuildId || config.allowedDiscordRoleIds.length === 0) {
    return null;
  }

  const response = await fetch(
    `${config.discordApiBaseUrl}/users/@me/guilds/${config.discordGuildId}/member`,
    {
      headers: {
        Authorization: `Bearer ${accessToken}`,
        Accept: "application/json"
      }
    }
  );

  if (response.status === 404 || response.status === 403) {
    return null;
  }

  if (!response.ok) {
    const raw = await response.text();
    throw new Error(`Discord guild member fetch failed: HTTP ${response.status} ${raw}`);
  }

  return response.json() as Promise<DiscordGuildMember>;
}

function isAllowedDiscordIdentity(user: DiscordUser, member: DiscordGuildMember | null) {
  const allowedByUserId = config.allowedDiscordUserIds.includes(user.id);
  const memberRoleIds = member?.roles ?? [];
  const allowedByRole =
    config.allowedDiscordRoleIds.length > 0 &&
    memberRoleIds.some(roleId => config.allowedDiscordRoleIds.includes(roleId));

  return {
    allowed: allowedByUserId || allowedByRole,
    allowedByUserId,
    allowedByRole,
    roleIds: memberRoleIds
  };
}

function loginHtml(errorMessage = "") {
  const disabled = discordOAuthConfigured() ? "" : "disabled";
  const hint = discordOAuthConfigured()
    ? "Melde dich mit Discord an. Zugriff wird gegen erlaubte User-IDs/Rollen geprüft."
    : "Discord OAuth ist noch nicht konfiguriert.";

  return `<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>JARVIS Dashboard Login</title>
  <style>
    :root { color-scheme: dark; font-family: Segoe UI, system-ui, sans-serif; }
    body { margin: 0; min-height: 100vh; display: grid; place-items: center; background: #0d1117; color: #e6edf3; }
    main { width: min(520px, calc(100vw - 32px)); border: 1px solid #30363d; border-radius: 16px; padding: 24px; background: #161b22; }
    a.button, button { display: block; text-align: center; text-decoration: none; width: 100%; box-sizing: border-box; padding: 12px; border-radius: 8px; border: 1px solid #5865f2; background: #5865f2; color: white; margin-top: 16px; font-weight: 700; }
    a.button.disabled { pointer-events: none; opacity: 0.5; }
    .error { color: #ff7b72; margin-top: 12px; }
    .muted { color: #8b949e; }
    code { background: #0d1117; border: 1px solid #30363d; border-radius: 6px; padding: 2px 6px; }
  </style>
</head>
<body>
  <main>
    <h1>JARVIS Dashboard</h1>
    <p class="muted">${escapeHtml(hint)}</p>
    <a class="button ${disabled}" href="/dashboard/auth/discord/start">Mit Discord einloggen</a>
    <p class="muted">Session-Timeout bei Inaktivität: <code>${config.dashboardSessionIdleSeconds}s</code></p>
    <p id="error" class="error">${escapeHtml(errorMessage)}</p>
  </main>
</body>
</html>`;
}

function dashboardHtml(sessionLabel: string) {
  return `<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>JARVIS Dashboard</title>
  <style>
    :root { color-scheme: dark; font-family: Segoe UI, system-ui, sans-serif; }
    body { margin: 0; background: #0d1117; color: #e6edf3; font-size: 15px; }
    header { padding: 24px max(24px, calc((100vw - 1680px) / 2)); border-bottom: 1px solid #30363d; background: #161b22; position: sticky; top: 0; z-index: 5; }
    header h1 { margin: 0 0 12px; font-size: clamp(28px, 3vw, 44px); }
    main { width: min(1680px, calc(100vw - 32px)); margin: 0 auto; display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(min(100%, 520px), 1fr)); padding: 24px 0 48px; align-items: start; }
    section { border: 1px solid #30363d; border-radius: 12px; padding: 16px; background: #161b22; min-height: 220px; }
    section h2 { margin-top: 0; font-size: 18px; }
    input, button { padding: 10px 12px; border-radius: 8px; border: 1px solid #30363d; background: #0d1117; color: #e6edf3; }
    button { cursor: pointer; background: #238636; border-color: #238636; font-weight: 600; }
    button.secondary { background: #21262d; border-color: #30363d; }
    pre { white-space: pre-wrap; overflow: auto; overflow-wrap: anywhere; background: #0d1117; padding: 12px; border-radius: 8px; border: 1px solid #30363d; max-height: 520px; min-height: 80px; font-size: 13px; line-height: 1.45; }
    .row { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
    .muted { color: #8b949e; }
    @media (max-width: 700px) {
      body { font-size: 14px; }
      header { padding: 16px; }
      main { width: calc(100vw - 20px); padding-top: 12px; }
      section { padding: 12px; }
    }
  </style>
</head>
<body>
  <header>
    <h1>JARVIS Dashboard</h1>
    <p class="muted">Angemeldet als: ${escapeHtml(sessionLabel)}</p>
    <p class="muted">Session läuft bei Inaktivität nach ${config.dashboardSessionIdleSeconds / 60} Minuten ab.</p>
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

function redirectWithError(reply: FastifyReply, message: string) {
  const encoded = encodeURIComponent(message);
  return reply.redirect(`/dashboard/login?error=${encoded}`, 303);
}

export async function dashboardRoutes(server: FastifyInstance) {
  server.get("/dashboard/login", async (request, reply) => {
    const session = getDashboardSession(request, reply);

    if (session) {
      return reply.redirect("/dashboard", 303);
    }

    const query = request.query as { error?: string } | undefined;
    return reply.type("text/html; charset=utf-8").send(loginHtml(query?.error ?? ""));
  });

  server.get("/dashboard/auth/discord/start", async (_request, reply) => {
    if (!discordOAuthConfigured()) {
      return reply.code(500).type("text/html; charset=utf-8").send(
        loginHtml("Discord OAuth ist nicht vollständig konfiguriert.")
      );
    }

    if (config.allowedDiscordRoleIds.length > 0 && !config.discordGuildId) {
      return reply.code(500).type("text/html; charset=utf-8").send(
        loginHtml("JARVIS_DISCORD_GUILD_ID fehlt für Rollenprüfung.")
      );
    }

    const state = createDashboardOAuthState();
    reply.header("Set-Cookie", dashboardOAuthStateSetCookieHeader(state));
    return reply.redirect(discordAuthorizeUrl(state), 303);
  });

  server.get("/dashboard/auth/discord/callback", async (request, reply) => {
    const query = request.query as { code?: string; state?: string; error?: string } | undefined;

    reply.header("Set-Cookie", dashboardOAuthStateClearCookieHeader());

    if (query?.error) {
      return redirectWithError(reply, `Discord Login abgebrochen: ${query.error}`);
    }

    if (!query?.code || !verifyDashboardOAuthState(request, query.state)) {
      return redirectWithError(reply, "Discord OAuth State ungültig oder abgelaufen.");
    }

    try {
      const token = await exchangeDiscordCode(query.code);
      const user = await fetchDiscordUser(token.access_token);
      const member = await fetchDiscordGuildMember(token.access_token);
      const authorization = isAllowedDiscordIdentity(user, member);

      if (!authorization.allowed) {
        request.log.warn(
          {
            discordUserId: user.id,
            allowedByUserId: authorization.allowedByUserId,
            allowedByRole: authorization.allowedByRole
          },
          "Dashboard Discord login denied"
        );

        return redirectWithError(reply, "Discord Account ist nicht für JARVIS Dashboard freigegeben.");
      }

      const session = createDashboardSession({
        discordUserId: user.id,
        username: user.username,
        globalName: user.global_name ?? undefined,
        roleIds: authorization.roleIds
      });

      reply.header("Set-Cookie", dashboardSessionSetCookieHeader(session.token));

      request.log.info(
        {
          discordUserId: user.id,
          allowedByUserId: authorization.allowedByUserId,
          allowedByRole: authorization.allowedByRole
        },
        "Dashboard Discord login successful"
      );

      return reply.redirect("/dashboard", 303);
    } catch (error) {
      request.log.error({ error }, "Dashboard Discord OAuth failed");
      return redirectWithError(reply, "Discord Login fehlgeschlagen. Prüfe Backend-Logs und OAuth-Konfiguration.");
    }
  });

  server.post("/dashboard/logout", async (request, reply) => {
    destroyDashboardSession(request);
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
    async (request, reply) => {
      const session = getDashboardSession(request, reply);
      const label = session
        ? `${session.globalName || session.username || "Discord User"} (${session.discordUserId})`
        : "Discord Session";

      return reply.type("text/html; charset=utf-8").send(dashboardHtml(label));
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
      const sessionStatus = getDashboardSessionStatus();

      return {
        ok: true,
        overview: {
          service: "jarvis-backend",
          now: new Date().toISOString(),
          runtimeState: runtime.state,
          publicBaseUrl: config.publicBaseUrl,
          dashboardSession: sessionStatus,
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
        dashboardSession: sessionStatus,
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

      const session = getDashboardSession(request, reply);
      const actorId = session?.discordUserId ?? "dashboard";

      const command = addCommand({
        id: createCommandId(),
        correlationId: createCorrelationId(),
        type: "morning_routine",
        status: "pending",
        requestedBy: `dashboard:${actorId}`,
        source: "dashboard",
        discordUserId: session?.discordUserId,
        discordRoleIds: session?.roleIds ?? [],
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
          id: actorId
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
