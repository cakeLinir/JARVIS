import { config } from "../config/config.js";

export type RealtimeClientSecretRequest = {
  model?: string;
  voice?: string;
  instructions?: string;
  modalities?: string[];
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
    const message =
      typeof parsed === "object" && parsed !== null && "error" in parsed
        ? JSON.stringify(parsed)
        : raw;
    throw new Error(`OpenAI HTTP ${response.status}: ${message}`);
  }

  return parsed as T;
}

// ✅ FIX: Korrekter Endpoint /realtime/sessions (nicht /realtime/client_secrets)
// ✅ FIX: Korrektes Request-Body-Format ohne session-Wrapper und ohne audio.output-Nesting
export async function createRealtimeClientSecret(
  input: RealtimeClientSecretRequest = {}
) {
  const sessionConfig = {
    model: input.model ?? config.realtimeModel,
    voice: input.voice ?? config.realtimeVoice,
    instructions: input.instructions ?? config.realtimeInstructions,
    modalities: input.modalities ?? ["text", "audio"],
    input_audio_transcription: {
      model: "whisper-1"
    },
    turn_detection: {
      type: "server_vad",
      threshold: 0.5,
      prefix_padding_ms: 300,
      silence_duration_ms: 500
    }
  };

  return openAiFetch("/realtime/sessions", sessionConfig);
}

export async function createChatCompletion(input: ChatRequest) {
  return openAiFetch("/chat/completions", {
    model: input.model ?? config.openAiChatModel,
    messages: input.messages,
    temperature: input.temperature ?? 0.2
  });
}
