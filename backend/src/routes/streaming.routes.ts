import type { FastifyInstance } from "fastify";
import { requireAnyJarvisAuth } from "../security/auth.js";
import { getStreamingAdvice } from "../services/streaming-advice.service.js";
import { addDays } from "../types/shift.types.js";

function todayStr(): string {
  return new Date().toISOString().slice(0, 10);
}

export async function streamingRoutes(server: FastifyInstance) {

  // GET /api/streaming/advice/today
  server.get("/api/streaming/advice/today", { preHandler: requireAnyJarvisAuth }, async () => {
    return { ok: true, advice: getStreamingAdvice(todayStr()) };
  });

  // GET /api/streaming/advice/tomorrow
  server.get("/api/streaming/advice/tomorrow", { preHandler: requireAnyJarvisAuth }, async () => {
    return { ok: true, advice: getStreamingAdvice(addDays(todayStr(), 1)) };
  });

  // GET /api/streaming/advice?date=YYYY-MM-DD
  server.get("/api/streaming/advice", { preHandler: requireAnyJarvisAuth }, async (req, reply) => {
    const { date } = req.query as { date?: string };
    const target = date ?? todayStr();
    if (!/^\d{4}-\d{2}-\d{2}$/.test(target)) {
      return reply.code(400).send({ error: "invalid_date_format", hint: "YYYY-MM-DD" });
    }
    return { ok: true, advice: getStreamingAdvice(target) };
  });

  // GET /api/streaming/advice/week — Vorschau nächste 7 Tage
  server.get("/api/streaming/advice/week", { preHandler: requireAnyJarvisAuth }, async () => {
    const today = todayStr();
    const advice = Array.from({ length: 7 }, (_, i) => getStreamingAdvice(addDays(today, i)));
    return { ok: true, count: advice.length, advice };
  });
}
