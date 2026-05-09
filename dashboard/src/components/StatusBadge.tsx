type Props = {
  value: unknown;
};

function classify(value: unknown): "ok" | "warn" | "bad" | "info" {
  const normalized = String(value ?? "unknown").toLowerCase();

  if (["ok", "online", "ready", "healthy", "running", "accepted"].includes(normalized)) {
    return "ok";
  }

  if (["unknown", "stale", "pending", "warning", "queued"].includes(normalized)) {
    return "warn";
  }

  if (["offline", "stopped", "failed", "error", "interrupted", "denied"].includes(normalized)) {
    return "bad";
  }

  return "info";
}

export function StatusBadge({ value }: Props) {
  return <span className={`badge ${classify(value)}`}>{String(value ?? "unknown")}</span>;
}
