import type { FastifyInstance } from "fastify";
import { requireAnyJarvisAuth } from "../security/auth.js";
import { getStreamingAdvice } from "../services/streaming-advice.service.js";
import { getTodayDateStr, getTomorrowDateStr } from "../services/shift-store.js";
import { addDays } from "../types/shift.types.js";

export async function streamingRoutes(server: FastifyInstance) {

    // GET /api/streaming/advice/today
    server.get("/api/streaming/advice/today", { preHandler: requireAnyJarvisAuth }, async () => {
        return { ok: true, advice: getStreamingAdvice(getTodayDateStr()) };
    });

    // GET /api/streaming/advice/tomorrow
    server.get("/api/streaming/advice/tomorrow", { preHandler: requireAnyJarvisAuth }, async () => {
        return { ok: true, advice: getStreamingAdvice(getTomorrowDateStr()) };
    });

    // GET /api/streaming/advice?date=YYYY-MM-DD
    server.get("/api/streaming/advice", { preHandler: requireAnyJarvisAuth }, async (req, reply) => {
        const { date } = req.query as { date?: string };
        const target = date ?? getTodayDateStr();

        if (!/^\d{4}-\d{2}-\d{2}$/.test(target)) {
            return reply.code(400).send({ error: "invalid_date_format", hint: "YYYY-MM-DD" });
        }
        return { ok: true, advice: getStreamingAdvice(target) };
    });

    // GET /api/streaming/advice/week — Vorschau nächste 7 Tage
    server.get("/api/streaming/advice/week", { preHandler: requireAnyJarvisAuth }, async () => {
        const today = getTodayDateStr();
        const days = Array.from({ length: 7 }, (_, i) => addDays(today, i));
        const advice = days.map(d => getStreamingAdvice(d));
        return { ok: true, count: advice.length, advice };
    });
}
