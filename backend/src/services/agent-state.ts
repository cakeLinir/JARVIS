export type AgentStatus = {
  agentName: string;
  hostname?: string;
  status: string;
  timestamp?: string;
  receivedAt: string;
};

export type MorningLog = {
  timestamp: string;
  startedApps: string[];
  failedApps: string[];
  todos: string[];
  projectSummary?: string;
  receivedAt: string;
};

let lastAgentStatus: AgentStatus | null = null;
let lastMorningLog: MorningLog | null = null;

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
