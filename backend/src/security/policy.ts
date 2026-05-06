import { config } from "../config/config.js";

type CommandType = "morning_routine" | "dev_news" | "app_open" | "system_stop";

type PolicyInput = {
  type: CommandType;
  discordUserId?: string;
  discordRoleIds: string[];
};

type PolicyResult = {
  allowed: boolean;
  reason?: string;
};

const rateLimitMap = new Map<string, number[]>();

function isConfiguredAllowedUser(userId: string | undefined): boolean {
  if (!userId) {
    return false;
  }

  return config.allowedDiscordUserIds.includes(userId);
}

function hasConfiguredAllowedRole(roleIds: string[]): boolean {
  if (config.allowedDiscordRoleIds.length === 0) {
    return false;
  }

  return roleIds.some(roleId => config.allowedDiscordRoleIds.includes(roleId));
}

function hasExplicitPermission(input: PolicyInput): boolean {
  return (
    isConfiguredAllowedUser(input.discordUserId) ||
    hasConfiguredAllowedRole(input.discordRoleIds)
  );
}

function isPlaceholderConfigured(): boolean {
  return config.allowedDiscordUserIds.some(item =>
    item.includes("CHANGE_ME")
  );
}

function checkRateLimit(input: PolicyInput): PolicyResult {
  const key = input.discordUserId ?? "unknown";
  const now = Date.now();

  const windowMs = config.commandRateLimitWindowSeconds * 1000;
  const maxHits = config.commandRateLimitMax;

  const existing = rateLimitMap.get(key) ?? [];
  const recent = existing.filter(timestamp => now - timestamp < windowMs);

  if (recent.length >= maxHits) {
    return {
      allowed: false,
      reason: `Rate-Limit erreicht: maximal ${maxHits} Commands pro ${config.commandRateLimitWindowSeconds}s.`
    };
  }

  recent.push(now);
  rateLimitMap.set(key, recent);

  return {
    allowed: true
  };
}

function requireExplicitPermission(input: PolicyInput): PolicyResult {
  if (isPlaceholderConfigured()) {
    return {
      allowed: false,
      reason: "JARVIS_ALLOWED_DISCORD_USER_IDS enthält noch CHANGE_ME_DISCORD_USER_ID."
    };
  }

  if (!hasExplicitPermission(input)) {
    return {
      allowed: false,
      reason: "Discord-User oder Discord-Rolle ist nicht für lokale JARVIS-Aktionen berechtigt."
    };
  }

  return checkRateLimit(input);
}

export function evaluateCommandPolicy(input: PolicyInput): PolicyResult {
  if (input.type === "dev_news") {
    return checkRateLimit(input);
  }

  if (["morning_routine", "app_open", "system_stop"].includes(input.type)) {
    return requireExplicitPermission(input);
  }

  return {
    allowed: false,
    reason: "Unbekannter Command-Typ."
  };
}
