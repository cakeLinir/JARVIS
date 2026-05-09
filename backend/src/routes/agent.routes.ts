import type { FastifyInstance } from "fastify";
import { z } from "zod";
import { requireAgentAuth, requireAnyJarvisAuth } from "../security/auth.js";
import {
  getAgentStatus,
  getMorningLog,
  setAgentStatus,
  setMorningLog
} from "../services/agent-state.js";

const AgentStatusSchema = z.object({
  agentName: z.string().min(1),
  hostname: z.string().optional(),
  status: z.string().min(1),
  timestamp: z.string().optional()
});

const TodoStatusSchema = z.object({
  provider: z.string().optional(),
  total: z.number().int().nonnegative().optional(),
  open: z.number().int().nonnegative().optional(),
  dueTodayOrUnscheduled: z.number().int().nonnegative().optional(),
  items: z.array(z.unknown()).optional(),
  errorCode: z.string().optional(),
  message: z.string().optional()
}).passthrough();

const MorningLogSchema = z.object({
  timestamp: z.string(),
  startedApps: z.array(z.string()).default([]),
  failedApps: z.array(z.string()).default([]),
  todos: z.array(z.string()).default([]),
  todoProvider: z.string().optional(),
  todoStatus: TodoStatusSchema.optional(),
  projectSummary: z.string().optional()
});

export async function agentRoutes(server: FastifyInstance) {
  server.post(
    "/api/agent/status",
    {
      preHandler: requireAgentAuth
    },
    async (request, reply) => {
      const parsed = AgentStatusSchema.safeParse(request.body);

      if (!parsed.success) {
        return reply.code(400).send({
          error: "invalid_agent_status_payload",
          details: parsed.error.flatten()
        });
      }

      const status = setAgentStatus(parsed.data);

      request.log.info({ status }, "Agent status received");

      return {
        ok: true,
        receivedAt: status.receivedAt
      };
    }
  );

  server.get(
    "/api/agent/status",
    {
      preHandler: requireAnyJarvisAuth
    },
    async () => {
      return {
        ok: true,
        status: getAgentStatus()
      };
    }
  );

  server.post(
    "/api/agent/morning-log",
    {
      preHandler: requireAgentAuth
    },
    async (request, reply) => {
      const parsed = MorningLogSchema.safeParse(request.body);

      if (!parsed.success) {
        return reply.code(400).send({
          error: "invalid_morning_log_payload",
          details: parsed.error.flatten()
        });
      }

      const morningLog = setMorningLog(parsed.data);

      request.log.info(
        {
          todoProvider: morningLog.todoProvider,
          todoCount: morningLog.todos.length,
          receivedAt: morningLog.receivedAt
        },
        "Morning log received"
      );

      return {
        ok: true,
        receivedAt: morningLog.receivedAt
      };
    }
  );

  server.get(
    "/api/agent/morning-log",
    {
      preHandler: requireAnyJarvisAuth
    },
    async () => {
      return {
        ok: true,
        morningLog: getMorningLog()
      };
    }
  );
}
