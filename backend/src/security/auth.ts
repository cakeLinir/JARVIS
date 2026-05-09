import type { FastifyRequest, FastifyReply } from "fastify";
import { timingSafeEqual } from "node:crypto";
import { config, isConfiguredSecret } from "../config/config.js";

function extractBearerToken(request: FastifyRequest): string | null {
  const authHeader = request.headers.authorization;

  if (!authHeader || !authHeader.startsWith("Bearer ")) {
    return null;
  }

  return authHeader.replace("Bearer ", "").trim();
}

function isUsableToken(token: string): boolean {
  return isConfiguredSecret(token);
}

function safeEquals(a: string, b: string): boolean {
  const left = Buffer.from(a);
  const right = Buffer.from(b);

  if (left.length !== right.length) {
    return false;
  }

  return timingSafeEqual(left, right);
}

async function requireAnyToken(
  request: FastifyRequest,
  reply: FastifyReply,
  allowedTokens: string[],
  errorName: string
) {
  const token = extractBearerToken(request);

  if (!token) {
    return reply.code(401).send({
      error: "missing_authorization_header"
    });
  }

  const validTokens = allowedTokens.filter(isUsableToken);

  if (!validTokens.some(validToken => safeEquals(token, validToken))) {
    return reply.code(403).send({
      error: errorName
    });
  }
}

export async function requireAgentAuth(
  request: FastifyRequest,
  reply: FastifyReply
) {
  return requireAnyToken(
    request,
    reply,
    [config.agentToken],
    "invalid_agent_token"
  );
}

export async function requireBotAuth(
  request: FastifyRequest,
  reply: FastifyReply
) {
  return requireAnyToken(
    request,
    reply,
    [config.botBridgeToken],
    "invalid_bot_bridge_token"
  );
}

export async function requireDashboardAuth(
  request: FastifyRequest,
  reply: FastifyReply
) {
  return requireAnyToken(
    request,
    reply,
    [config.dashboardToken],
    "invalid_dashboard_token"
  );
}

export async function requireAgentOrBotAuth(
  request: FastifyRequest,
  reply: FastifyReply
) {
  return requireAnyToken(
    request,
    reply,
    [config.agentToken, config.botBridgeToken],
    "invalid_token"
  );
}

export async function requireAgentOrDashboardAuth(
  request: FastifyRequest,
  reply: FastifyReply
) {
  return requireAnyToken(
    request,
    reply,
    [config.agentToken, config.dashboardToken],
    "invalid_token"
  );
}

export async function requireBotOrDashboardAuth(
  request: FastifyRequest,
  reply: FastifyReply
) {
  return requireAnyToken(
    request,
    reply,
    [config.botBridgeToken, config.dashboardToken],
    "invalid_token"
  );
}

export async function requireAnyJarvisAuth(
  request: FastifyRequest,
  reply: FastifyReply
) {
  return requireAnyToken(
    request,
    reply,
    [config.agentToken, config.botBridgeToken, config.dashboardToken],
    "invalid_token"
  );
}
