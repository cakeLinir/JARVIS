import type { FastifyInstance } from "fastify";
import { getDevNews, getNewsSources } from "../services/news.service.js";

export async function newsRoutes(server: FastifyInstance) {
  server.get("/api/news/dev", async (request, reply) => {
    const query = request.query as { refresh?: string } | undefined;
    const forceRefresh = query?.refresh === "true";

    try {
      const news = await getDevNews(forceRefresh);

      return {
        ok: true,
        status: "ready",
        fetchedAt: news.fetchedAt,
        fromCache: news.fromCache,
        sources: getNewsSources(),
        items: news.items,
        errors: news.errors
      };
    } catch (error) {
      request.log.error({ error }, "Dev news fetch failed");
      return reply.code(502).send({
        ok: false,
        error: "dev_news_fetch_failed",
        message: error instanceof Error ? error.message : String(error),
        sources: getNewsSources()
      });
    }
  });
}
