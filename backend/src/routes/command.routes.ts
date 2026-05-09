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
  createCorrelationId,
  findCommandById,
  getCommandStorePath,
  getNextPendingCommand,
  getRecentCommands,
  updateCommand,
  type CommandSource,
  type JarvisCommand
} from "../services/command-store.js";
import { appendAuditEvent } from "../services/audit-log.js";

const AllowedCommandTypes = z.enum([
  "morning_routine",
  "dev_news",
  "app_open",
  "system_stop"
]);

const AllowedCommandSources = z.enum([
  "discord",
  "dashboard",
  "agent",
  "backend",
  "local",
  "unknown"
]);

const CreateCommandSchema = z.object({
  type: AllowedCommandTypes,
  requestedBy: z.string().min(1).default("unknown"),
  source: AllowedCommandSources.optional(),
  discordUserId: z.string().optional(),
  discordRoleIds: z.array(z.string()).default([]),
  payload: z.record(z.unknown()).default({})
});

const CompleteCommandSchema = z.object({
  status: z.enum(["completed", "failed", "rejected"]),
  result: z.string().optional(),
  errorCode: z.string().optional(),
  details: z.unknown().optional()
});

function resolveCommandSource(input: z.infer<typeof CreateCommandSchema>): CommandSource {
  if (input.source) {
    return input.source;
  }

  const sourceFromPayload = input.payload.source;

  if (typeof sourceFromPayload === "string") {
    const parsed = AllowedCommandSources.safeParse(sourceFromPayload);

    if (parsed.success) {
      return parsed.data;
    }
  }

  if (input.discordUserId) {
    return "discord";
  }

  if (input.requestedBy === "dashboard") {
    return "dashboard";
  }

  return "unknown";
}

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

      const commandSource = resolveCommandSource(parsed.data);

      const baseCommand: JarvisCommand = {
        id: createCommandId(),
        correlationId: createCorrelationId(),
        type: parsed.data.type,
        status: policy.allowed ? "pending" : "rejected",
        source: commandSource,
        requestedBy: parsed.data.requestedBy,
        discordUserId: parsed.data.discordUserId,
        discordRoleIds: parsed.data.discordRoleIds,
        payload: parsed.data.payload,
        createdAt: new Date().toISOString()
      };

      if (!policy.allowed) {
        baseCommand.errorCode = "command_rejected_by_policy";
        baseCommand.completedAt = new Date().toISOString();
        baseCommand.rejectionReason = policy.reason;
        baseCommand.result = policy.reason;
      }

      const command = addCommand(baseCommand);

      appendAuditEvent({
        component: "backend",
        action: "command.create",
        result: policy.allowed ? "accepted" : "rejected",
        commandId: command.id,
        correlationId: command.correlationId,
        actor: {
          type: "bot",
          id: parsed.data.discordUserId ?? parsed.data.requestedBy
        },
        errorCode: policy.allowed ? undefined : "command_rejected_by_policy",
        message: policy.allowed
          ? `Command akzeptiert: ${command.type}`
          : policy.reason,
        details: {
          type: command.type,
          source: command.source,
          requestedBy: command.requestedBy
        }
      });

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

      if (!command.correlationId) {
        command.correlationId = createCorrelationId();
      }

      command.status = "claimed";
      command.claimedAt = new Date().toISOString();
      command.claimedBy = agentName;
      command.attempts = (command.attempts ?? 0) + 1;

      appendAuditEvent({
        component: "backend",
        action: "command.claim",
        result: "claimed",
        commandId: command.id,
        correlationId: command.correlationId,
        actor: {
          type: "agent",
          id: agentName
        },
        message: `Command von Agent geclaimt: ${agentName}`
      });

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
      command.errorCode = parsed.data.errorCode;
      command.details = parsed.data.details;

      updateCommand(command);

      request.log.info({ command }, "Command completed");

      appendAuditEvent({
        component: "backend",
        action: "command.complete",
        result: parsed.data.status,
        commandId: command.id,
        correlationId: command.correlationId,
        actor: {
          type: "agent",
          id: command.claimedBy
        },
        errorCode: parsed.data.errorCode,
        message: parsed.data.result,
        details: parsed.data.details
      });

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
