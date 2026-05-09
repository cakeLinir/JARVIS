export type RuntimeState =
  | "unknown"
  | "online"
  | "stale"
  | "offline"
  | "stopped"
  | "interrupted"
  | string;

export type RuntimeStatus = {
  state?: RuntimeState;
  lastStatus?: string | null;
  lastReceivedAt?: string | null;
  ageSeconds?: number | null;
  staleAfterSeconds?: number;
  offlineAfterSeconds?: number;
};

export type AgentStatus = {
  agentName?: string;
  hostname?: string;
  status?: string;
  timestamp?: string;
  receivedAt?: string;
};

export type TodoItem = {
  id?: string;
  title?: string;
  status?: string;
  dueDate?: string | null;
  priority?: number;
  source?: string;
};

export type TodoOverview = {
  status?: string;
  provider?: string | null;
  total?: number | null;
  open?: number | null;
  dueTodayOrUnscheduled?: number | null;
  items?: Array<TodoItem | string>;
  lastUpdatedAt?: string;
  message?: string;
};

export type ConfigCheck = {
  key: string;
  configured: boolean;
  required: boolean;
  message: string;
};

export type ConfigurationStatus = {
  ok?: boolean;
  summary?: {
    total: number;
    missingRequired: number;
  };
  public?: Record<string, unknown>;
  checks?: ConfigCheck[];
};

export type CommandItem = {
  id?: string;
  correlationId?: string;
  type?: string;
  status?: string;
  requestedBy?: string;
  source?: string;
  createdAt?: string;
};

export type AuditItem = {
  timestamp?: string;
  component?: string;
  action?: string;
  result?: string;
  message?: string;
  commandId?: string;
  correlationId?: string;
};

export type MorningLog = {
  timestamp?: string;
  startedApps?: string[];
  failedApps?: string[];
  todos?: string[];
  todoProvider?: string;
  projectSummary?: string;
  receivedAt?: string;
};

export type DashboardSessionStatus = {
  mode?: string;
  active?: number | null;
  idleTimeoutSeconds?: number;
};

export type DashboardOverviewResponse = {
  ok: boolean;
  overview?: {
    service?: string;
    now?: string;
    runtimeState?: string;
    publicBaseUrl?: string;
    realtimeModel?: string;
    realtimeVoice?: string;
    commandCounts?: Record<string, number>;
    configurationSummary?: {
      total: number;
      missingRequired: number;
    };
    todoProvider?: string | null;
    todoOpen?: number | null;
    dashboardSession?: DashboardSessionStatus;
  };
  runtime?: RuntimeStatus;
  configuration?: ConfigurationStatus;
  dashboardSession?: DashboardSessionStatus;
  todo?: TodoOverview;
  agentStatus?: AgentStatus | null;
  morningLog?: MorningLog | null;
  recentCommands?: CommandItem[];
  recentAuditEvents?: AuditItem[];
};
