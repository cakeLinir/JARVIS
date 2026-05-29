import type { FastifyInstance } from "fastify";
import { z } from "zod";
import { requireAnyJarvisAuth } from "../security/auth.js";
import { createClaudeCompletion } from "../services/claude.service.js";

const ChatSchema = z.object({
  model: z.string().optional(),
  system: z.string().optional(),
  maxTokens: z.number().int().min(1).max(128000).optional(),
  messages: z.array(
    z.object({
      role: z.enum(["user", "assistant"]),
      content: z.string().min(1),
    })
  ).min(1),
});

export async function claudeRoutes(server: FastifyInstance) {
  server.post(
    "/api/claude/chat",
    { preHandler: requireAnyJarvisAuth },
    async (request, reply) => {
      const parsed = ChatSchema.safeParse(request.body);

      if (!parsed.success) {
        return reply.code(400).send({
          ok: false,
          error: "invalid_chat_payload",
          details: parsed.error.flatten(),
        });
      }

      try {
        const response = await createClaudeCompletion(parsed.data);
        const textBlock = response.content.find(b => b.type === "text");
        return {
          ok: true,
          response,
          text: textBlock && textBlock.type === "text" ? textBlock.text : null,
        };
      } catch (error) {
        request.log.error({ error }, "Claude chat failed");
        return reply.code(502).send({
          ok: false,
          error: "claude_chat_failed",
          message: error instanceof Error ? error.message : String(error),
        });
      }
    }
  );
}
