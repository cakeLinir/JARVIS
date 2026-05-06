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

export const config = {
  port: numberFromEnv(process.env.JARVIS_BACKEND_PORT, 8080),
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
