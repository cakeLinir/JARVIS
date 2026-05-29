import dotenv from "dotenv";

dotenv.config();

function splitCsv(value: string | undefined): string[] {
  if (!value) {
    return [];
  }

  return value
    .split(",")
    .map(item => item.trim())
    .filter(Boolean);
}

function numberFromEnv(value: string | undefined, fallback: number): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function booleanFromEnv(value: string | undefined, fallback: boolean): boolean {
  if (!value) {
    return fallback;
  }

  const normalized = value.trim().toLowerCase();

  if (["1", "true", "yes", "y", "on"].includes(normalized)) {
    return true;
  }

  if (["0", "false", "no", "n", "off"].includes(normalized)) {
    return false;
  }

  return fallback;
}

export function isUsableSecret(value: string | undefined): boolean {
  if (!value) {
    return false;
  }

  const normalized = value.trim();

  if (!normalized) {
    return false;
  }

  const upper = normalized.toUpperCase();
  const invalidMarkers = [
    "CHANGE_ME",
    "PLACEHOLDER",
    "EXAMPLE",
    "DEIN_",
    "YOUR_",
    "TOKEN_HERE"
  ];

  if (invalidMarkers.some(marker => upper.includes(marker))) {
    return false;
  }

  return normalized.length >= 16;
}

function publicBaseUrlFromEnv(): string {
  const explicit = process.env.JARVIS_PUBLIC_BASE_URL?.trim();

  if (explicit) {
    return explicit.replace(/\/+$/, "");
  }

  const host = process.env.JARVIS_PUBLIC_HOST?.trim() || "jarvis.hundekuchenlive.de";
  const port = numberFromEnv(process.env.JARVIS_BACKEND_PORT, 8181);
  return host === "jarvis.hundekuchenlive.de" ? "https://jarvis.hundekuchenlive.de" : `http://${host}:${port}`;
}

const publicBaseUrl = publicBaseUrlFromEnv();

export const config = {
  host: process.env.JARVIS_BACKEND_HOST?.trim() || "127.0.0.1",
  port: numberFromEnv(process.env.JARVIS_BACKEND_PORT, 8181),
  publicBaseUrl,

  agentToken: process.env.JARVIS_AGENT_TOKEN ?? "",
  botBridgeToken: process.env.JARVIS_BOT_BRIDGE_TOKEN ?? "",
  dashboardToken: process.env.JARVIS_DASHBOARD_TOKEN ?? "",
  openAiApiKey: process.env.OPENAI_API_KEY ?? "",
  anthropicApiKey: process.env.ANTHROPIC_API_KEY ?? "",

  dashboardSessionCookieName:
    process.env.JARVIS_DASHBOARD_SESSION_COOKIE_NAME?.trim() ||
    "jarvis_dashboard_session",
  dashboardStateCookieName:
    process.env.JARVIS_DASHBOARD_STATE_COOKIE_NAME?.trim() ||
    "jarvis_dashboard_oauth_state",
  dashboardSessionTtlSeconds: numberFromEnv(
    process.env.JARVIS_DASHBOARD_SESSION_TTL_SECONDS,
    60 * 30
  ),
  dashboardSessionIdleSeconds: numberFromEnv(
    process.env.JARVIS_DASHBOARD_SESSION_IDLE_SECONDS,
    60 * 30
  ),
  dashboardOAuthStateTtlSeconds: numberFromEnv(
    process.env.JARVIS_DASHBOARD_OAUTH_STATE_TTL_SECONDS,
    10 * 60
  ),
  dashboardCookieSecure: booleanFromEnv(
    process.env.JARVIS_DASHBOARD_COOKIE_SECURE,
    publicBaseUrl.startsWith("https://")
  ),

  discordOAuthClientId: process.env.JARVIS_DISCORD_OAUTH_CLIENT_ID?.trim() ?? "",
  discordOAuthClientSecret: process.env.JARVIS_DISCORD_OAUTH_CLIENT_SECRET ?? "",
  discordOAuthRedirectUri:
    process.env.JARVIS_DISCORD_OAUTH_REDIRECT_URI?.trim() ||
    `${publicBaseUrl}/dashboard/auth/discord/callback`,
  discordGuildId: process.env.JARVIS_DISCORD_GUILD_ID?.trim() ?? "",
  discordApiBaseUrl:
    process.env.JARVIS_DISCORD_API_BASE_URL?.trim() ||
    "https://discord.com/api",

  realtimeModel: process.env.JARVIS_REALTIME_MODEL ?? "gpt-4o-realtime-preview",
  realtimeVoice: process.env.JARVIS_REALTIME_VOICE ?? "verse",
  realtimeInstructions:
    process.env.JARVIS_REALTIME_INSTRUCTIONS ??
    "Du bist JARVIS, ein deutscher persönlicher Windows-Desktop-Assistent. Antworte kurz, präzise und führe Aktionen nur über freigegebene Tools aus.",

  openAiChatModel: process.env.JARVIS_OPENAI_CHAT_MODEL ?? "gpt-4.1-mini",
  claudeModel: process.env.JARVIS_CLAUDE_MODEL ?? "claude-opus-4-8",

  allowedDiscordUserIds: splitCsv(process.env.JARVIS_ALLOWED_DISCORD_USER_IDS),
  allowedDiscordRoleIds: splitCsv(process.env.JARVIS_ALLOWED_DISCORD_ROLE_IDS),

  commandRateLimitWindowSeconds: numberFromEnv(
    process.env.JARVIS_COMMAND_RATE_LIMIT_WINDOW_SECONDS,
    60
  ),

  commandRateLimitMax: numberFromEnv(
    process.env.JARVIS_COMMAND_RATE_LIMIT_MAX,
    3
  ),

  commandClaimTimeoutSeconds: numberFromEnv(
    process.env.JARVIS_COMMAND_CLAIM_TIMEOUT_SECONDS,
    120
  ),

  newsCacheTtlSeconds: numberFromEnv(
    process.env.JARVIS_NEWS_CACHE_TTL_SECONDS,
    900
  ),

  newsMaxItems: numberFromEnv(process.env.JARVIS_NEWS_MAX_ITEMS, 12)
};

type ConfigCheck = {
  key: string;
  configured: boolean;
  required: boolean;
  message: string;
};

function checkSecret(key: string, value: string, required = true): ConfigCheck {
  const configured = isUsableSecret(value);

  return {
    key,
    configured,
    required,
    message: configured
      ? `${key} ist gesetzt.`
      : `${key} fehlt oder ist noch ein Platzhalter.`
  };
}

function hasNoPlaceholderItems(items: string[]): boolean {
  return (
    items.length > 0 &&
    !items.some(item => item.toUpperCase().includes("CHANGE_ME"))
  );
}

export function getConfigStatus() {
  const roleAuthRequired = config.allowedDiscordRoleIds.length > 0;

  const checks: ConfigCheck[] = [
    {
      key: "JARVIS_BACKEND_HOST",
      configured: Boolean(config.host),
      required: true,
      message: `Backend bindet auf ${config.host}.`
    },
    {
      key: "JARVIS_BACKEND_PORT",
      configured: config.port === 8181,
      required: true,
      message:
        config.port === 8181
          ? "Backend-Port ist projektkonform 8181."
          : `Backend-Port ist ${config.port}; Projektstandard ist 8181.`
    },
    {
      key: "JARVIS_PUBLIC_BASE_URL",
      configured: Boolean(config.publicBaseUrl),
      required: true,
      message: "Public Base URL ist konfiguriert."
    },
    checkSecret("ANTHROPIC_API_KEY", config.anthropicApiKey),
    checkSecret("OPENAI_API_KEY", config.openAiApiKey, false),
    checkSecret("JARVIS_AGENT_TOKEN", config.agentToken),
    checkSecret("JARVIS_BOT_BRIDGE_TOKEN", config.botBridgeToken),
    checkSecret("JARVIS_DASHBOARD_TOKEN", config.dashboardToken, false),
    {
      key: "JARVIS_DISCORD_OAUTH_CLIENT_ID",
      configured: Boolean(config.discordOAuthClientId),
      required: true,
      message: config.discordOAuthClientId
        ? "Discord OAuth Client-ID ist gesetzt."
        : "Discord OAuth Client-ID fehlt."
    },
    checkSecret(
      "JARVIS_DISCORD_OAUTH_CLIENT_SECRET",
      config.discordOAuthClientSecret
    ),
    {
      key: "JARVIS_DISCORD_OAUTH_REDIRECT_URI",
      configured: Boolean(config.discordOAuthRedirectUri),
      required: true,
      message: "Discord OAuth Redirect-URI ist gesetzt."
    },
    {
      key: "JARVIS_DISCORD_GUILD_ID",
      configured: Boolean(config.discordGuildId),
      required: roleAuthRequired,
      message: roleAuthRequired
        ? "Discord Guild-ID ist für Rollenprüfung erforderlich."
        : "Discord Guild-ID ist optional, solange keine Rollenprüfung aktiv ist."
    },
    {
      key: "JARVIS_ALLOWED_DISCORD_USER_IDS",
      configured: hasNoPlaceholderItems(config.allowedDiscordUserIds),
      required: config.allowedDiscordRoleIds.length === 0,
      message:
        config.allowedDiscordUserIds.length > 0
          ? "Discord User-Allowlist ist gesetzt."
          : "Discord User-Allowlist fehlt."
    },
    {
      key: "JARVIS_ALLOWED_DISCORD_ROLE_IDS",
      configured:
        config.allowedDiscordRoleIds.length === 0 ||
        hasNoPlaceholderItems(config.allowedDiscordRoleIds),
      required: false,
      message:
        config.allowedDiscordRoleIds.length > 0
          ? "Discord Rollen-Allowlist ist gesetzt."
          : "Discord Rollen-Allowlist ist leer; Zugriff läuft über User-ID."
    },
    {
      key: "JARVIS_DASHBOARD_SESSION_IDLE_SECONDS",
      configured: config.dashboardSessionIdleSeconds === 1800,
      required: true,
      message:
        config.dashboardSessionIdleSeconds === 1800
          ? "Dashboard Idle-Timeout ist 30 Minuten."
          : `Dashboard Idle-Timeout ist ${config.dashboardSessionIdleSeconds}s; gewünscht sind 1800s.`
    }
  ];

  const missingRequired = checks.filter(
    item => item.required && !item.configured
  );

  return {
    ok: missingRequired.length === 0,
    summary: {
      total: checks.length,
      missingRequired: missingRequired.length
    },
    public: {
      host: config.host,
      port: config.port,
      publicBaseUrl: config.publicBaseUrl,
      dashboardCookieSecure: config.dashboardCookieSecure,
      dashboardSessionIdleSeconds: config.dashboardSessionIdleSeconds
    },
    checks
  };
}

export function logConfigWarnings(log: {
  warn: (value: unknown, message?: string) => void;
  info: (value: unknown, message?: string) => void;
}) {
  const status = getConfigStatus();

  if (status.ok) {
    log.info(
      {
        host: config.host,
        port: config.port,
        publicBaseUrl: config.publicBaseUrl
      },
      "JARVIS configuration looks complete"
    );
    return;
  }

  log.warn(
    {
      missingRequired: status.summary.missingRequired,
      checks: status.checks
        .filter(item => item.required && !item.configured)
        .map(item => ({
          key: item.key,
          message: item.message
        }))
    },
    "JARVIS configuration is incomplete"
  );
}
