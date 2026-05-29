import Anthropic from "@anthropic-ai/sdk";
import { config } from "../config/config.js";

export type ClaudeMessage = {
  role: "user" | "assistant";
  content: string;
};

export type ClaudeRequest = {
  messages: ClaudeMessage[];
  system?: string;
  model?: string;
  maxTokens?: number;
};

let _client: Anthropic | null = null;

function getClient(): Anthropic {
  if (!_client) {
    if (!config.anthropicApiKey || config.anthropicApiKey.length < 16 || config.anthropicApiKey.includes("CHANGE_ME")) {
      throw new Error("ANTHROPIC_API_KEY ist nicht gesetzt.");
    }
    _client = new Anthropic({ apiKey: config.anthropicApiKey });
  }
  return _client;
}

export async function createClaudeCompletion(input: ClaudeRequest) {
  const client = getClient();
  const model = input.model ?? config.claudeModel;

  const params: Anthropic.MessageCreateParams = {
    model,
    max_tokens: input.maxTokens ?? 4096,
    messages: input.messages.map(m => ({ role: m.role, content: m.content })),
  };

  if (input.system) {
    // Cache the system prompt — it stays stable across requests
    params.system = [
      {
        type: "text",
        text: input.system,
        cache_control: { type: "ephemeral" },
      },
    ];
  }

  return client.messages.create(params);
}
