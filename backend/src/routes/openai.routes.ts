import type { FastifyInstance } from "fastify";
import { z } from "zod";
import { requireAnyJarvisAuth } from "../security/auth.js";
import { createChatCompletion } from "../services/openai.service.js";

const ChatSchema = z.object({
  model: z.string().optional(),
  temperature: z.number().min(0).max(2).optional(),
  messages: z.array(
    z.object({
      role: z.enum(["system", "user", "assistant"]),
      content: z.string().min(1)
    })
  ).min(1)
});

export async function openAiRoutes(server: FastifyInstance) {
  server.post(
    "/api/openai/chat",
    {
      preHandler: requireAnyJarvisAuth
    },
    async (request, reply) => {
      const parsed = ChatSchema.safeParse(request.body);

      if (!parsed.success) {
        return reply.code(400).send({
          ok: false,
          error: "invalid_chat_payload",
          details: parsed.error.flatten()
        });
      }

      try {
        const response = await createChatCompletion(parsed.data);
        return {
          ok: true,
          response
        };
      } catch (error) {
        request.log.error({ error }, "OpenAI chat failed");
        return reply.code(502).send({
          ok: false,
          error: "openai_chat_failed",
          message: error instanceof Error ? error.message : String(error)
        });
      }
    }
  );
}
