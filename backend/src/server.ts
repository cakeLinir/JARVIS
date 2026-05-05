import Fastify from "fastify";

const server = Fastify({
  logger: true
});

server.get("/api/health", async () => {
  return {
    status: "ok",
    service: "jarvis-backend",
    timestamp: new Date().toISOString()
  };
});

async function start() {
  const port = Number(process.env.JARVIS_BACKEND_PORT ?? 8080);

  try {
    await server.listen({
      port,
      host: "0.0.0.0"
    });
  } catch (error) {
    server.log.error(error);
    process.exit(1);
  }
}

start();
