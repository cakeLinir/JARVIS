import type { FastifyRequest, FastifyReply } from "fastify";
import { createHmac, timingSafeEqual } from "node:crypto";
import { config, isUsableSecret } from "../config/config.js";

type DashboardSessionPayload = {
  type: "dashboard";
  iat: number;
  exp: number;
};

function base64UrlEncode(value: string | Buffer): string {
  return Buffer.from(value)
    .toString("base64url");
}

function base64UrlDecode(value: string): string {
  return Buffer.from(value, "base64url").toString("utf-8");
}

function extractBearerToken(request: FastifyRequest): string | null {
  const authHeader = request.headers.authorization;

  if (!authHeader || !authHeader.startsWith("Bearer ")) {
    return null;
  }

  return authHeader.replace("Bearer ", "").trim();
}

function safeEquals(a: string, b: string): boolean {
  const left = Buffer.from(a);
  const right = Buffer.from(b);

  if (left.length !== right.length) {
    return false;
  }

  return timingSafeEqual(left, right);
}

function tokenMatches(candidate: string | null, validToken: string): boolean {
  if (!candidate || !isUsableSecret(validToken)) {
    return false;
  }

  return safeEquals(candidate, validToken);
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

  const validTokens = allowedTokens.filter(isUsableSecret);

  if (!validTokens.some(validToken => safeEquals(token, validToken))) {
    return reply.code(403).send({
      error: errorName
    });
  }
}

function parseCookies(request: FastifyRequest): Record<string, string> {
  const raw = request.headers.cookie;

  if (!raw) {
    return {};
  }

  const result: Record<string, string> = {};

  for (const part of raw.split(";")) {
    const index = part.indexOf("=");

    if (index <= 0) {
      continue;
    }

    const key = part.slice(0, index).trim();
    const value = part.slice(index + 1).trim();

    if (key) {
      result[key] = decodeURIComponent(value);
    }
  }

  return result;
}

function signPayload(encodedPayload: string): string {
  return createHmac("sha256", config.dashboardToken)
    .update(encodedPayload)
    .digest("base64url");
}

export function createDashboardSessionCookie(): string {
  const now = Math.floor(Date.now() / 1000);
  const payload: DashboardSessionPayload = {
    type: "dashboard",
    iat: now,
    exp: now + config.dashboardSessionTtlSeconds
  };

  const encodedPayload = base64UrlEncode(JSON.stringify(payload));
  const signature = signPayload(encodedPayload);
  return `${encodedPayload}.${signature}`;
}

function verifyDashboardSessionCookie(value: string | undefined): boolean {
  if (!value || !isUsableSecret(config.dashboardToken)) {
    return false;
  }

  const [encodedPayload, signature] = value.split(".");

  if (!encodedPayload || !signature) {
    return false;
  }

  const expectedSignature = signPayload(encodedPayload);

  if (!safeEquals(signature, expectedSignature)) {
    return false;
  }

  try {
    const payload = JSON.parse(base64UrlDecode(encodedPayload)) as DashboardSessionPayload;

    if (payload.type !== "dashboard") {
      return false;
    }

    const now = Math.floor(Date.now() / 1000);
    return payload.exp > now;
  } catch {
    return false;
  }
}

export function dashboardSessionSetCookieHeader(sessionValue: string): string {
  const parts = [
    `${config.dashboardSessionCookieName}=${encodeURIComponent(sessionValue)}`,
    "HttpOnly",
    "SameSite=Strict",
    "Path=/",
    `Max-Age=${config.dashboardSessionTtlSeconds}`
  ];

  if (config.dashboardCookieSecure) {
    parts.push("Secure");
  }

  return parts.join("; ");
}

export function dashboardSessionClearCookieHeader(): string {
  return [
    `${config.dashboardSessionCookieName}=`,
    "HttpOnly",
    "SameSite=Strict",
    "Path=/",
    "Max-Age=0"
  ].join("; ");
}

export function isDashboardRequestAuthorized(request: FastifyRequest): boolean {
  const bearerToken = extractBearerToken(request);

  if (tokenMatches(bearerToken, config.dashboardToken)) {
    return true;
  }

  const cookies = parseCookies(request);
  return verifyDashboardSessionCookie(cookies[config.dashboardSessionCookieName]);
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
  if (!isDashboardRequestAuthorized(request)) {
    return reply.code(401).send({
      error: "dashboard_auth_required"
    });
  }
}

export async function requireDashboardWebAuth(
  request: FastifyRequest,
  reply: FastifyReply
) {
  if (!isDashboardRequestAuthorized(request)) {
    return reply.redirect("/dashboard/login", 303);
  }
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
  const bearerToken = extractBearerToken(request);

  if (
    tokenMatches(bearerToken, config.agentToken) ||
    isDashboardRequestAuthorized(request)
  ) {
    return;
  }

  return reply.code(403).send({
    error: "invalid_token"
  });
}

export async function requireBotOrDashboardAuth(
  request: FastifyRequest,
  reply: FastifyReply
) {
  const bearerToken = extractBearerToken(request);

  if (
    tokenMatches(bearerToken, config.botBridgeToken) ||
    isDashboardRequestAuthorized(request)
  ) {
    return;
  }

  return reply.code(403).send({
    error: "invalid_token"
  });
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
