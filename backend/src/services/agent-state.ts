export type AgentStatus = {
  agentName: string;
  hostname?: string;
  status: string;
  timestamp?: string;
  receivedAt: string;
};

export type TodoStatus = {
  provider?: string;
  total?: number;
  open?: number;
  dueTodayOrUnscheduled?: number;
  items?: unknown[];
  errorCode?: string;
  message?: string;
};

export type MorningLog = {
  timestamp: string;
  startedApps: string[];
  failedApps: string[];
  todos: string[];
  todoProvider?: string;
  todoStatus?: TodoStatus;
  projectSummary?: string;
  receivedAt: string;
};

export type AgentRuntimeState =
  | "unknown"
  | "online"
  | "stale"
  | "offline"
  | "stopped"
  | "interrupted";

export type AgentRuntimeStatus = {
  state: AgentRuntimeState;
  lastStatus: string | null;
  lastReceivedAt: string | null;
  ageSeconds: number | null;
  staleAfterSeconds: number;
  offlineAfterSeconds: number;
};

let lastAgentStatus: AgentStatus | null = null;
let lastMorningLog: MorningLog | null = null;

function ageSecondsFromIso(value: string | null): number | null {
  if (!value) {
    return null;
  }

  const parsed = Date.parse(value);
  if (!Number.isFinite(parsed)) {
    return null;
  }

  return Math.max(0, Math.floor((Date.now() - parsed) / 1000));
}

function normalizeRuntimeState(status: string | null): AgentRuntimeState | null {
  if (!status) {
    return null;
  }

  const normalized = status.trim().toLowerCase();

  if (normalized === "stopped") {
    return "stopped";
  }

  if (normalized === "offline") {
    return "offline";
  }

  if (normalized === "interrupted") {
    return "interrupted";
  }

  return null;
}

export function setAgentStatus(status: Omit<AgentStatus, "receivedAt">): AgentStatus {
  lastAgentStatus = {
    ...status,
    receivedAt: new Date().toISOString()
  };

  return lastAgentStatus;
}

export function getAgentStatus(): AgentStatus | null {
  return lastAgentStatus;
}

export function getAgentRuntimeStatus(options: {
  staleAfterSeconds?: number;
  offlineAfterSeconds?: number;
} = {}): AgentRuntimeStatus {
  const staleAfterSeconds = options.staleAfterSeconds ?? 45;
  const offlineAfterSeconds = options.offlineAfterSeconds ?? 180;

  if (!lastAgentStatus) {
    return {
      state: "unknown",
      lastStatus: null,
      lastReceivedAt: null,
      ageSeconds: null,
      staleAfterSeconds,
      offlineAfterSeconds
    };
  }

  const explicitState = normalizeRuntimeState(lastAgentStatus.status);
  const ageSeconds = ageSecondsFromIso(lastAgentStatus.receivedAt);

  if (explicitState) {
    return {
      state: explicitState,
      lastStatus: lastAgentStatus.status,
      lastReceivedAt: lastAgentStatus.receivedAt,
      ageSeconds,
      staleAfterSeconds,
      offlineAfterSeconds
    };
  }

  let state: AgentRuntimeState = "online";

  if (ageSeconds === null) {
    state = "unknown";
  } else if (ageSeconds > offlineAfterSeconds) {
    state = "offline";
  } else if (ageSeconds > staleAfterSeconds) {
    state = "stale";
  }

  return {
    state,
    lastStatus: lastAgentStatus.status,
    lastReceivedAt: lastAgentStatus.receivedAt,
    ageSeconds,
    staleAfterSeconds,
    offlineAfterSeconds
  };
}

export function setMorningLog(log: Omit<MorningLog, "receivedAt">): MorningLog {
  lastMorningLog = {
    ...log,
    receivedAt: new Date().toISOString()
  };

  return lastMorningLog;
}

export function getMorningLog(): MorningLog | null {
  return lastMorningLog;
}
