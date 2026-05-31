export interface ChatResponse {
  ok: boolean;
  answer: string | null;
  toolCalls: { name: string; input: Record<string, unknown> }[];
  historyTurns: number;
  spoken: boolean;
}

export interface ChatResetResponse {
  ok: boolean;
  cleared: boolean;
  historyTurns: number;
}

function agentUrl(path: string, base: string): string {
  return base.replace(/\/$/, "") + path;
}

export async function sendChatMessage(
  text: string,
  speak: boolean,
  agentBase: string,
  token: string
): Promise<ChatResponse> {
  const res = await fetch(agentUrl("/actions/chat", agentBase), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ text, speak }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { error?: string }).error ?? `HTTP_${res.status}`);
  }
  return res.json() as Promise<ChatResponse>;
}

export async function resetChatHistory(
  agentBase: string,
  token: string
): Promise<ChatResetResponse> {
  const res = await fetch(agentUrl("/actions/chat/reset", agentBase), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: "{}",
  });
  if (!res.ok) throw new Error(`HTTP_${res.status}`);
  return res.json() as Promise<ChatResetResponse>;
}
