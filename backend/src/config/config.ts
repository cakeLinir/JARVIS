import dotenv from "dotenv";

dotenv.config();

export type ConfigSeverity = "ok" | "warning" | "error";

export type ConfigCheck = {
  key: string;
  label: string;
  ok: boolean;
  severity: ConfigSeverity;
  required: boolean;
  sensitive: boolean;
  message: string;
};

export type ConfigStatus = {
  ok: boolean;
  generatedAt: string;
  backend: {
    host: string;
    port: number;
  };
  summary: {
    ok: number;
    warnings: number;
    errors: number;
  };
  checks: ConfigCheck[];
};

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

function normalized(value: string | undefined): string {
  return (value ?? "").trim();
}

export function isPlaceholderValue(value: string | undefined): boolean {
  const item = normalized(value);

  if (!item) {
    return false;
  }

  const upper = item.toUpperCase();

  return (
    upper.includes("CHANGE_ME") ||
    upper.includes("NUR_LOKAL") ||
    upper.includes("DEIN_") ||
    upper.includes("YOUR_") ||
    upper === "TOKEN" ||
    upper === "SECRET" ||
    upper === "API_KEY"
  );
}

export function isConfiguredSecret(value: string | undefined): boolean {
  const item = normalized(value);

  if (!item) {
    return false;
  }

  return !isPlaceholderValue(item);
}

function hasConfiguredListValue(values: string[]): boolean {
  return values.some(value => isConfiguredSecret(value));
}

function secretCheck(
  key: string,
  label: string,
  value: string | undefined,
  required: boolean,
  missingMessage: string
): ConfigCheck {
  const ok = isConfiguredSecret(value);

  return {
    key,
    label,
    ok,
    required,
    sensitive: true,
    severity: ok ? "ok" : required ? "error" : "warning",
    message: ok ? "Konfiguriert." : missingMessage
  };
}

function booleanCheck(
  key: string,
  label: string,
  ok: boolean,
  required: boolean,
  missingMessage: string
): ConfigCheck {
  return {
    key,
    label,
    ok,
    required,
    sensitive: false,
    severity: ok ? "ok" : required ? "error" : "warning",
    message: ok ? "Konfiguriert." : missingMessage
  };
}

export const config = {
  host: process.env.JARVIS_BACKEND_HOST ?? "0.0.0.0",
  port: numberFromEnv(process.env.JARVIS_BACKEND_PORT, 8181),
  agentToken: process.env.JARVIS_AGENT_TOKEN ?? "",
  botBridgeToken: process.env.JARVIS_BOT_BRIDGE_TOKEN ?? "",
  dashboardToken: process.env.JARVIS_DASHBOARD_TOKEN ?? "",
  openAiApiKey: process.env.OPENAI_API_KEY ?? "",

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

export function getConfigChecks(): ConfigCheck[] {
  return [
    booleanCheck(
      "backend.host",
      "Backend Host",
      Boolean(normalized(config.host)),
      true,
      "JARVIS_BACKEND_HOST fehlt."
    ),
    booleanCheck(
      "backend.port",
      "Backend Port",
      Number.isInteger(config.port) && config.port > 0 && config.port <= 65535,
      true,
      "JARVIS_BACKEND_PORT ist ungültig."
    ),
    secretCheck(
      "secrets.agentToken",
      "Agent Token",
      config.agentToken,
      true,
      "JARVIS_AGENT_TOKEN fehlt oder enthält noch einen Platzhalter."
    ),
    secretCheck(
      "secrets.botBridgeToken",
      "Bot Bridge Token",
      config.botBridgeToken,
      true,
      "JARVIS_BOT_BRIDGE_TOKEN fehlt oder enthält noch einen Platzhalter."
    ),
    secretCheck(
      "secrets.dashboardToken",
      "Dashboard Token",
      config.dashboardToken,
      true,
      "JARVIS_DASHBOARD_TOKEN fehlt oder enthält noch einen Platzhalter."
    ),
    secretCheck(
      "secrets.openAiApiKey",
      "OpenAI API Key",
      config.openAiApiKey,
      false,
      "OPENAI_API_KEY fehlt. OpenAI-Chat und Realtime-Secret funktionieren dann nicht."
    ),
    booleanCheck(
      "discord.allowedActors",
      "Discord erlaubte User/Rollen",
      hasConfiguredListValue(config.allowedDiscordUserIds) ||
        hasConfiguredListValue(config.allowedDiscordRoleIds),
      false,
      "Keine erlaubte Discord-User-ID oder Rollen-ID konfiguriert. Discord-Commands für lokale Aktionen werden abgelehnt."
    )
  ];
}

export function getConfigStatus(): ConfigStatus {
  const checks = getConfigChecks();
  const errors = checks.filter(item => !item.ok && item.severity === "error").length;
  const warnings = checks.filter(item => !item.ok && item.severity === "warning").length;
  const ok = checks.filter(item => item.ok).length;

  return {
    ok: errors === 0,
    generatedAt: new Date().toISOString(),
    backend: {
      host: config.host,
      port: config.port
    },
    summary: {
      ok,
      warnings,
      errors
    },
    checks
  };
}

export function getStartupConfigWarnings(): string[] {
  return getConfigChecks()
    .filter(item => !item.ok)
    .map(item => `${item.key}: ${item.message}`);
}
