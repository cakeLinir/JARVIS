import fs from "node:fs";
import path from "node:path";
import { randomUUID } from "node:crypto";

export type AuditActorType =
  | "agent"
  | "bot"
  | "dashboard"
  | "backend"
  | "system"
  | "unknown";

export type AuditResult =
  | "accepted"
  | "claimed"
  | "completed"
  | "failed"
  | "rejected"
  | "expired"
  | "skipped"
  | "error";

export type AuditActor = {
  type: AuditActorType;
  id?: string;
};

export type AuditEvent = {
  id: string;
  timestamp: string;
  component: string;
  action: string;
  result: AuditResult;
  commandId?: string;
  correlationId?: string;
  actor?: AuditActor;
  errorCode?: string;
  message?: string;
  details?: unknown;
};

export type AuditEventInput = Omit<AuditEvent, "id" | "timestamp"> & {
  id?: string;
  timestamp?: string;
};

const dataDir = path.resolve(process.cwd(), ".runtime", "data");
const auditPath = path.join(dataDir, "audit-log.jsonl");

function ensureAuditStoreExists() {
  if (!fs.existsSync(dataDir)) {
    fs.mkdirSync(dataDir, { recursive: true });
  }

  if (!fs.existsSync(auditPath)) {
    fs.writeFileSync(auditPath, "", "utf-8");
  }
}

function parseAuditLine(line: string): AuditEvent | null {
  try {
    const parsed = JSON.parse(line) as AuditEvent;

    if (!parsed.id || !parsed.timestamp || !parsed.action || !parsed.result) {
      return null;
    }

    return parsed;
  } catch {
    return null;
  }
}

export function appendAuditEvent(input: AuditEventInput): AuditEvent {
  ensureAuditStoreExists();

  const event: AuditEvent = {
    id: input.id ?? `aud_${randomUUID()}`,
    timestamp: input.timestamp ?? new Date().toISOString(),
    component: input.component,
    action: input.action,
    result: input.result,
    commandId: input.commandId,
    correlationId: input.correlationId,
    actor: input.actor,
    errorCode: input.errorCode,
    message: input.message,
    details: input.details
  };

  fs.appendFileSync(auditPath, `${JSON.stringify(event)}\n`, "utf-8");
  return event;
}

export function getRecentAuditEvents(limit = 50): AuditEvent[] {
  ensureAuditStoreExists();

  const raw = fs.readFileSync(auditPath, "utf-8");
  const lines = raw
    .split(/\r?\n/)
    .map(line => line.trim())
    .filter(Boolean);

  return lines
    .reverse()
    .map(parseAuditLine)
    .filter((event): event is AuditEvent => event !== null)
    .slice(0, limit);
}

export function getAuditStorePath(): string {
  ensureAuditStoreExists();
  return auditPath;
}
