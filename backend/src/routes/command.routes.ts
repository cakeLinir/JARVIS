import type { FastifyInstance } from "fastify";
import { z } from "zod";
import {
  requireAgentAuth,
  requireAnyJarvisAuth,
  requireBotAuth
} from "../security/auth.js";
import { evaluateCommandPolicy } from "../security/policy.js";
import {
  addCommand,
  createCommandId,
  findCommandById,
  getCommandStorePath,
  getNextPendingCommand,
  getRecentCommands,
  updateCommand,
  type JarvisCommand
} from "../services/command-store.js";

const AllowedCommandTypes = z.enum([
  "morning_routine",
  "dev_news",
  "app_open",
  "system_stop"
]);

const CreateCommandSchema = z.object({
  type: AllowedCommandTypes,
  requestedBy: z.string().min(1).default("unknown"),
  discordUserId: z.string().optional(),
  discordRoleIds: z.array(z.string()).default([]),
  payload: z.record(z.unknown()).default({})
});

const CompleteCommandSchema = z.object({
  status: z.enum(["completed", "failed", "rejected"]),
  result: z.string().optional(),
  details: z.unknown().optional()
});

export async function commandRoutes(server: FastifyInstance) {
  server.post(
    "/api/commands",
    {
      preHandler: requireBotAuth
    },
    async (request, reply) => {
      const parsed = CreateCommandSchema.safeParse(request.body);

      if (!parsed.success) {
        return reply.code(400).send({
          error: "invalid_command_payload",
          details: parsed.error.flatten()
        });
      }

      const policy = evaluateCommandPolicy({
        type: parsed.data.type,
        discordUserId: parsed.data.discordUserId,
        discordRoleIds: parsed.data.discordRoleIds
      });

      const baseCommand: JarvisCommand = {
        id: createCommandId(),
        type: parsed.data.type,
        status: policy.allowed ? "pending" : "rejected",
        requestedBy: parsed.data.requestedBy,
        discordUserId: parsed.data.discordUserId,
        discordRoleIds: parsed.data.discordRoleIds,
        payload: parsed.data.payload,
        createdAt: new Date().toISOString()
      };

      if (!policy.allowed) {
        baseCommand.completedAt = new Date().toISOString();
        baseCommand.rejectionReason = policy.reason;
        baseCommand.result = policy.reason;
      }

      const command = addCommand(baseCommand);

      request.log.info({ command }, "Command stored");

      if (!policy.allowed) {
        return reply.code(403).send({
          ok: false,
          error: "command_rejected_by_policy",
          reason: policy.reason,
          command
        });
      }

      return {
        ok: true,
        command
      };
    }
  );

  server.get(
    "/api/commands/next",
    {
      preHandler: requireAgentAuth
    },
    async (request) => {
      const query = request.query as { agentName?: string } | undefined;
      const agentName = query?.agentName ?? "unknown-agent";

      const command = getNextPendingCommand();

      if (!command) {
        return {
          ok: true,
          command: null
        };
      }

      command.status = "claimed";
      command.claimedAt = new Date().toISOString();
      command.claimedBy = agentName;

      updateCommand(command);

      request.log.info({ command }, "Command claimed");

      return {
        ok: true,
        command
      };
    }
  );

  server.post(
    "/api/commands/:id/complete",
    {
      preHandler: requireAgentAuth
    },
    async (request, reply) => {
      const params = request.params as { id: string };
      const parsed = CompleteCommandSchema.safeParse(request.body);

      if (!parsed.success) {
        return reply.code(400).send({
          error: "invalid_command_complete_payload",
          details: parsed.error.flatten()
        });
      }

      const command = findCommandById(params.id);

      if (!command) {
        return reply.code(404).send({
          error: "command_not_found"
        });
      }

      command.status = parsed.data.status;
      command.completedAt = new Date().toISOString();
      command.result = parsed.data.result;
      command.details = parsed.data.details;

      updateCommand(command);

      request.log.info({ command }, "Command completed");

      return {
        ok: true,
        command
      };
    }
  );

  server.get(
    "/api/commands/recent",
    {
      preHandler: requireAnyJarvisAuth
    },
    async () => {
      return {
        ok: true,
        storePath: getCommandStorePath(),
        commands: getRecentCommands()
      };
    }
  );
}
