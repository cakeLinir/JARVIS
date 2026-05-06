export type RealtimeSessionOptions = {
  backendUrl: string;
  agentToken: string;
  model?: string;
  voice?: string;
};

export async function getRealtimeClientSecret(options: RealtimeSessionOptions) {
  const response = await fetch(`${options.backendUrl.replace(/\/$/, "")}/api/realtime/client-secret`, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${options.agentToken}`,
      "Content-Type": "application/json",
      "Accept": "application/json"
    },
    body: JSON.stringify({
      model: options.model,
      voice: options.voice
    })
  });

  const payload = await response.json();

  if (!response.ok || !payload.ok) {
    throw new Error(payload.message ?? payload.error ?? `Backend HTTP ${response.status}`);
  }

  return payload.secret;
}

export async function callLocalMorningRoutine(localApiUrl: string, localApiToken: string) {
  const response = await fetch(`${localApiUrl.replace(/\/$/, "")}/actions/morning`, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${localApiToken}`,
      "Content-Type": "application/json",
      "Accept": "application/json"
    },
    body: JSON.stringify({ confirm: "START" })
  });

  const payload = await response.json();

  if (!response.ok || !payload.ok) {
    throw new Error(payload.message ?? payload.error ?? `Local API HTTP ${response.status}`);
  }

  return payload;
}
