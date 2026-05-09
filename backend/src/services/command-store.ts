import fs from "node:fs";
import path from "node:path";
import { config } from "../config/config.js";
import { appendAuditEvent } from "./audit-log.js";

export type CommandStatus =
  | "pending"
  | "claimed"
  | "completed"
  | "failed"
  | "rejected"
  | "expired";

export type CommandSource =
  | "discord"
  | "dashboard"
  | "agent"
  | "backend"
  | "local"
  | "unknown";

export type JarvisCommand = {
  id: string;
  correlationId?: string;
  type: "morning_routine" | "dev_news" | "app_open" | "system_stop";
  status: CommandStatus;
  source?: CommandSource;
  requestedBy: string;
  discordUserId?: string;
  discordRoleIds: string[];
  payload: Record<string, unknown>;
  createdAt: string;
  claimedAt?: string;
  claimedBy?: string;
  completedAt?: string;
  attempts?: number;
  result?: string;
  details?: unknown;
  rejectionReason?: string;
  errorCode?: string;
};

const dataDir = path.resolve(process.cwd(), ".runtime", "data");
const storePath = path.join(dataDir, "commands.json");

let commands: JarvisCommand[] = [];

function ensureStoreExists() {
  if (!fs.existsSync(dataDir)) {
    fs.mkdirSync(dataDir, { recursive: true });
  }

  if (!fs.existsSync(storePath)) {
    fs.writeFileSync(storePath, "[]", "utf-8");
  }
}

export function loadCommands() {
  ensureStoreExists();

  try {
    const raw = fs.readFileSync(storePath, "utf-8");
    const parsed = JSON.parse(raw);

    if (Array.isArray(parsed)) {
      commands = parsed;
      resetExpiredClaimedCommands();
      return;
    }

    commands = [];
    saveCommands();
  } catch {
    const backupPath = `${storePath}.broken-${Date.now()}.bak`;

    if (fs.existsSync(storePath)) {
      fs.copyFileSync(storePath, backupPath);
    }

    commands = [];
    saveCommands();
  }
}

export function saveCommands() {
  ensureStoreExists();

  const tempPath = `${storePath}.tmp`;
  fs.writeFileSync(tempPath, JSON.stringify(commands, null, 2), "utf-8");
  fs.renameSync(tempPath, storePath);
}

export function createCommandId(): string {
  const random = Math.random().toString(16).slice(2, 10);
  return `cmd_${Date.now()}_${random}`;
}

export function createCorrelationId(): string {
  const random = Math.random().toString(16).slice(2, 10);
  return `corr_${Date.now()}_${random}`;
}

export function addCommand(command: JarvisCommand): JarvisCommand {
  commands.push(command);
  saveCommands();
  return command;
}

function isClaimExpired(command: JarvisCommand, now = Date.now()): boolean {
  if (command.status !== "claimed" || !command.claimedAt) {
    return false;
  }

  const claimedAtMs = Date.parse(command.claimedAt);

  if (!Number.isFinite(claimedAtMs)) {
    return true;
  }

  return now - claimedAtMs > config.commandClaimTimeoutSeconds * 1000;
}

export function resetExpiredClaimedCommands(): number {
  const now = Date.now();
  let changed = 0;

  for (const command of commands) {
    if (isClaimExpired(command, now)) {
      command.status = "pending";
      command.result = `Command wurde nach ${config.commandClaimTimeoutSeconds}s Claim-Timeout erneut freigegeben.`;
      command.details = {
        ...(typeof command.details === "object" && command.details !== null ? command.details : {}),
        previousClaimedAt: command.claimedAt,
        previousClaimedBy: command.claimedBy,
        requeuedAt: new Date().toISOString()
      };
      appendAuditEvent({
        component: "backend",
        action: "command.claim_expired",
        result: "expired",
        commandId: command.id,
        correlationId: command.correlationId,
        actor: {
          type: "system"
        },
        errorCode: "command_claim_timeout",
        message: `Command wurde nach ${config.commandClaimTimeoutSeconds}s Claim-Timeout erneut freigegeben.`
      });
      command.claimedAt = undefined;
      command.claimedBy = undefined;
      changed += 1;
    }
  }

  if (changed > 0) {
    saveCommands();
  }

  return changed;
}

export function getNextPendingCommand(): JarvisCommand | null {
  resetExpiredClaimedCommands();
  return commands.find(item => item.status === "pending") ?? null;
}

export function findCommandById(id: string): JarvisCommand | null {
  return commands.find(item => item.id === id) ?? null;
}

export function getRecentCommands(limit = 20): JarvisCommand[] {
  resetExpiredClaimedCommands();

  return [...commands]
    .sort((a, b) => b.createdAt.localeCompare(a.createdAt))
    .slice(0, limit);
}

export function updateCommand(command: JarvisCommand): JarvisCommand {
  const index = commands.findIndex(item => item.id === command.id);

  if (index >= 0) {
    commands[index] = command;
  }

  saveCommands();
  return command;
}

export function getCommandStorePath(): string {
  ensureStoreExists();
  return storePath;
}

export function getCommandCounts(): Record<CommandStatus, number> {
  resetExpiredClaimedCommands();

  return commands.reduce(
    (result, command) => {
      result[command.status] += 1;
      return result;
    },
    {
      pending: 0,
      claimed: 0,
      completed: 0,
      failed: 0,
      rejected: 0,
      expired: 0
    } satisfies Record<CommandStatus, number>
  );
}
