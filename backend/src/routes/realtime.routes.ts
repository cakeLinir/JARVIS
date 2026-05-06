import type { FastifyInstance } from "fastify";
import { z } from "zod";
import { requireAgentAuth } from "../security/auth.js";
import { createRealtimeClientSecret } from "../services/openai.service.js";

const RealtimeSecretSchema = z.object({
  model: z.string().optional(),
  voice: z.string().optional(),
  instructions: z.string().optional()
});

export async function realtimeRoutes(server: FastifyInstance) {
  server.post(
    "/api/realtime/client-secret",
    {
      preHandler: requireAgentAuth
    },
    async (request, reply) => {
      const parsed = RealtimeSecretSchema.safeParse(request.body ?? {});

      if (!parsed.success) {
        return reply.code(400).send({
          ok: false,
          error: "invalid_realtime_secret_payload",
          details: parsed.error.flatten()
        });
      }

      try {
        const secret = await createRealtimeClientSecret(parsed.data);
        return {
          ok: true,
          secret
        };
      } catch (error) {
        request.log.error({ error }, "Realtime client secret creation failed");
        return reply.code(502).send({
          ok: false,
          error: "realtime_client_secret_failed",
          message: error instanceof Error ? error.message : String(error)
        });
      }
    }
  );
}
