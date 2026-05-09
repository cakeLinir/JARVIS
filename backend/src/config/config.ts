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

  const host = process.env.JARVIS_PUBLIC_HOST?.trim() || "46.225.14.84";
  const port = numberFromEnv(process.env.JARVIS_BACKEND_PORT, 8181);
  return `http://${host}:${port}`;
}

export const config = {
  host: process.env.JARVIS_BACKEND_HOST?.trim() || "0.0.0.0",
  port: numberFromEnv(process.env.JARVIS_BACKEND_PORT, 8181),
  publicBaseUrl: publicBaseUrlFromEnv(),

  agentToken: process.env.JARVIS_AGENT_TOKEN ?? "",
  botBridgeToken: process.env.JARVIS_BOT_BRIDGE_TOKEN ?? "",
  dashboardToken: process.env.JARVIS_DASHBOARD_TOKEN ?? "",
  openAiApiKey: process.env.OPENAI_API_KEY ?? "",

  dashboardSessionCookieName:
    process.env.JARVIS_DASHBOARD_SESSION_COOKIE_NAME?.trim() ||
    "jarvis_dashboard_session",
  dashboardSessionTtlSeconds: numberFromEnv(
    process.env.JARVIS_DASHBOARD_SESSION_TTL_SECONDS,
    60 * 60 * 8
  ),
  dashboardCookieSecure: booleanFromEnv(
    process.env.JARVIS_DASHBOARD_COOKIE_SECURE,
    publicBaseUrlFromEnv().startsWith("https://")
  ),

  realtimeModel: process.env.JARVIS_REALTIME_MODEL ?? "gpt-4o-realtime-preview",
  realtimeVoice: process.env.JARVIS_REALTIME_VOICE ?? "verse",
  realtimeInstructions:
    process.env.JARVIS_REALTIME_INSTRUCTIONS ??
    "Du bist JARVIS, ein deutscher persönlicher Windows-Desktop-Assistent. Antworte kurz, präzise und führe Aktionen nur über freigegebene Tools aus.",

  openAiChatModel: process.env.JARVIS_OPENAI_CHAT_MODEL ?? "gpt-4.1-mini",

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

export function getConfigStatus() {
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
      message: `Public Base URL ist konfiguriert.`
    },
    checkSecret("OPENAI_API_KEY", config.openAiApiKey),
    checkSecret("JARVIS_AGENT_TOKEN", config.agentToken),
    checkSecret("JARVIS_BOT_BRIDGE_TOKEN", config.botBridgeToken),
    checkSecret("JARVIS_DASHBOARD_TOKEN", config.dashboardToken),
    {
      key: "JARVIS_ALLOWED_DISCORD_USER_IDS",
      configured:
        config.allowedDiscordUserIds.length > 0 &&
        !config.allowedDiscordUserIds.some(item =>
          item.toUpperCase().includes("CHANGE_ME")
        ),
      required: true,
      message:
        config.allowedDiscordUserIds.length > 0
          ? "Discord User-Allowlist ist gesetzt."
          : "Discord User-Allowlist fehlt."
    },
    {
      key: "JARVIS_DASHBOARD_SESSION_TTL_SECONDS",
      configured: config.dashboardSessionTtlSeconds > 0,
      required: true,
      message: `Dashboard Session TTL ist gesetzt.`
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
      dashboardCookieSecure: config.dashboardCookieSecure
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
