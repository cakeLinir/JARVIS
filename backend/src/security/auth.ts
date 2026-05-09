import type { FastifyRequest, FastifyReply } from "fastify";
import { createHmac, randomBytes, timingSafeEqual } from "node:crypto";
import { config, isUsableSecret } from "../config/config.js";

export type DashboardSession = {
  token: string;
  discordUserId: string;
  username?: string;
  globalName?: string;
  roleIds: string[];
  createdAt: number;
  lastActivityAt: number;
  expiresAt: number;
};

type DashboardSessionPayload = {
  type: "dashboard";
  discordUserId: string;
  username?: string;
  globalName?: string;
  roleIds: string[];
  createdAt: number;
  lastActivityAt: number;
  expiresAt: number;
  nonce: string;
};

function nowMs(): number {
  return Date.now();
}

function randomToken(): string {
  return randomBytes(32).toString("base64url");
}

function base64UrlEncode(value: string): string {
  return Buffer.from(value, "utf-8").toString("base64url");
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

function cookieHeader(
  name: string,
  value: string,
  maxAgeSeconds: number,
  sameSite: "Strict" | "Lax" = "Lax"
): string {
  const parts = [
    `${name}=${encodeURIComponent(value)}`,
    "HttpOnly",
    `SameSite=${sameSite}`,
    "Path=/",
    `Max-Age=${maxAgeSeconds}`
  ];

  if (config.dashboardCookieSecure) {
    parts.push("Secure");
  }

  return parts.join("; ");
}

function clearCookieHeader(name: string): string {
  const parts = [
    `${name}=`,
    "HttpOnly",
    "SameSite=Lax",
    "Path=/",
    "Max-Age=0"
  ];

  if (config.dashboardCookieSecure) {
    parts.push("Secure");
  }

  return parts.join("; ");
}

function signPayload(encodedPayload: string): string {
  return createHmac("sha256", config.dashboardToken)
    .update(encodedPayload)
    .digest("base64url");
}

function createSignedSessionToken(payload: DashboardSessionPayload): string {
  const encodedPayload = base64UrlEncode(JSON.stringify(payload));
  const signature = signPayload(encodedPayload);
  return `${encodedPayload}.${signature}`;
}

function verifySignedSessionToken(token: string): DashboardSessionPayload | null {
  if (!isUsableSecret(config.dashboardToken)) {
    return null;
  }

  const [encodedPayload, signature] = token.split(".");

  if (!encodedPayload || !signature) {
    return null;
  }

  const expectedSignature = signPayload(encodedPayload);

  if (!safeEquals(signature, expectedSignature)) {
    return null;
  }

  try {
    const payload = JSON.parse(base64UrlDecode(encodedPayload)) as DashboardSessionPayload;

    if (payload.type !== "dashboard") {
      return null;
    }

    if (!payload.discordUserId || !payload.expiresAt || !payload.createdAt) {
      return null;
    }

    return payload;
  } catch {
    return null;
  }
}

export function createDashboardOAuthState(): string {
  return randomToken();
}

export function dashboardOAuthStateSetCookieHeader(state: string): string {
  return cookieHeader(
    config.dashboardStateCookieName,
    state,
    config.dashboardOAuthStateTtlSeconds,
    "Lax"
  );
}

export function dashboardOAuthStateClearCookieHeader(): string {
  return clearCookieHeader(config.dashboardStateCookieName);
}

export function verifyDashboardOAuthState(
  request: FastifyRequest,
  expectedState: string | undefined
): boolean {
  if (!expectedState) {
    return false;
  }

  const cookies = parseCookies(request);
  const storedState = cookies[config.dashboardStateCookieName];

  if (!storedState) {
    return false;
  }

  return safeEquals(storedState, expectedState);
}

export function createDashboardSession(input: {
  discordUserId: string;
  username?: string;
  globalName?: string;
  roleIds?: string[];
}): DashboardSession {
  const createdAt = nowMs();
  const expiresAt = createdAt + config.dashboardSessionIdleSeconds * 1000;
  const payload: DashboardSessionPayload = {
    type: "dashboard",
    discordUserId: input.discordUserId,
    username: input.username,
    globalName: input.globalName,
    roleIds: input.roleIds ?? [],
    createdAt,
    lastActivityAt: createdAt,
    expiresAt,
    nonce: randomToken()
  };

  const token = createSignedSessionToken(payload);

  return {
    token,
    discordUserId: payload.discordUserId,
    username: payload.username,
    globalName: payload.globalName,
    roleIds: payload.roleIds,
    createdAt: payload.createdAt,
    lastActivityAt: payload.lastActivityAt,
    expiresAt: payload.expiresAt
  };
}

export function destroyDashboardSession(_request: FastifyRequest): void {
  // Signed-cookie sessions are stateless. Logout clears the browser cookie.
}

export function dashboardSessionSetCookieHeader(sessionToken: string): string {
  return cookieHeader(
    config.dashboardSessionCookieName,
    sessionToken,
    config.dashboardSessionIdleSeconds,
    "Lax"
  );
}

export function dashboardSessionClearCookieHeader(): string {
  return clearCookieHeader(config.dashboardSessionCookieName);
}

export function getDashboardSession(
  request: FastifyRequest,
  reply?: FastifyReply
): DashboardSession | null {
  const cookies = parseCookies(request);
  const token = cookies[config.dashboardSessionCookieName];

  if (!token) {
    request.log.debug("Dashboard session cookie missing");
    return null;
  }

  const payload = verifySignedSessionToken(token);

  if (!payload) {
    request.log.warn("Dashboard session cookie invalid");
    if (reply) {
      reply.header("Set-Cookie", dashboardSessionClearCookieHeader());
    }
    return null;
  }

  const now = nowMs();

  if (payload.expiresAt <= now) {
    request.log.info({ discordUserId: payload.discordUserId }, "Dashboard session expired");

    if (reply) {
      reply.header("Set-Cookie", dashboardSessionClearCookieHeader());
    }

    return null;
  }

  const refreshedPayload: DashboardSessionPayload = {
    ...payload,
    lastActivityAt: now,
    expiresAt: now + config.dashboardSessionIdleSeconds * 1000
  };
  const refreshedToken = createSignedSessionToken(refreshedPayload);

  if (reply) {
    reply.header(
      "Set-Cookie",
      dashboardSessionSetCookieHeader(refreshedToken)
    );
  }

  return {
    token: refreshedToken,
    discordUserId: refreshedPayload.discordUserId,
    username: refreshedPayload.username,
    globalName: refreshedPayload.globalName,
    roleIds: refreshedPayload.roleIds,
    createdAt: refreshedPayload.createdAt,
    lastActivityAt: refreshedPayload.lastActivityAt,
    expiresAt: refreshedPayload.expiresAt
  };
}

export function getDashboardSessionStatus() {
  return {
    mode: "signed-cookie",
    active: null,
    idleTimeoutSeconds: config.dashboardSessionIdleSeconds
  };
}

export function isDashboardRequestAuthorized(
  request: FastifyRequest,
  reply?: FastifyReply
): boolean {
  const bearerToken = extractBearerToken(request);

  if (tokenMatches(bearerToken, config.dashboardToken)) {
    return true;
  }

  return Boolean(getDashboardSession(request, reply));
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
  if (!isDashboardRequestAuthorized(request, reply)) {
    return reply.code(401).send({
      error: "dashboard_auth_required"
    });
  }
}

export async function requireDashboardWebAuth(
  request: FastifyRequest,
  reply: FastifyReply
) {
  if (!isDashboardRequestAuthorized(request, reply)) {
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
    isDashboardRequestAuthorized(request, reply)
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
    isDashboardRequestAuthorized(request, reply)
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
