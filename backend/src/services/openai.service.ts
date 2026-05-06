import { config } from "../config/config.js";

export type RealtimeClientSecretRequest = {
  model?: string;
  voice?: string;
  instructions?: string;
};

export type ChatMessage = {
  role: "system" | "user" | "assistant";
  content: string;
};

export type ChatRequest = {
  messages: ChatMessage[];
  model?: string;
  temperature?: number;
};

function ensureOpenAiConfigured() {
  if (!config.openAiApiKey || config.openAiApiKey === "CHANGE_ME") {
    throw new Error("OPENAI_API_KEY ist nicht gesetzt.");
  }
}

async function openAiFetch<T>(endpoint: string, body: unknown): Promise<T> {
  ensureOpenAiConfigured();

  const response = await fetch(`https://api.openai.com/v1${endpoint}`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${config.openAiApiKey}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify(body)
  });

  const raw = await response.text();
  let parsed: unknown = raw;

  if (raw) {
    try {
      parsed = JSON.parse(raw);
    } catch {
      parsed = { raw };
    }
  }

  if (!response.ok) {
    const message = typeof parsed === "object" && parsed !== null && "error" in parsed
      ? JSON.stringify(parsed)
      : raw;
    throw new Error(`OpenAI HTTP ${response.status}: ${message}`);
  }

  return parsed as T;
}

export async function createRealtimeClientSecret(input: RealtimeClientSecretRequest = {}) {
  const sessionConfig = {
    session: {
      type: "realtime",
      model: input.model ?? config.realtimeModel,
      instructions: input.instructions ?? config.realtimeInstructions,
      audio: {
        output: {
          voice: input.voice ?? config.realtimeVoice
        }
      }
    }
  };

  return openAiFetch("/realtime/client_secrets", sessionConfig);
}

export async function createChatCompletion(input: ChatRequest) {
  return openAiFetch("/chat/completions", {
    model: input.model ?? config.openAiChatModel,
    messages: input.messages,
    temperature: input.temperature ?? 0.2
  });
}
