import type { FastifyInstance } from "fastify";

export async function healthRoutes(server: FastifyInstance) {
  server.get("/api/health", async () => {
    return {
      status: "ok",
      service: "jarvis-backend",
      timestamp: new Date().toISOString()
    };
  });
}
