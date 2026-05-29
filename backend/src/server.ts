import Fastify from "fastify";
import cors from "@fastify/cors";
import websocket from "@fastify/websocket";

import { config, logConfigWarnings } from "./config/config.js";
import { loadCommands } from "./services/command-store.js";

import { healthRoutes } from "./routes/health.routes.js";
import { agentRoutes } from "./routes/agent.routes.js";
import { newsRoutes } from "./routes/news.routes.js";
import { openAiRoutes } from "./routes/openai.routes.js";
import { commandRoutes } from "./routes/command.routes.js";
import { realtimeRoutes } from "./routes/realtime.routes.js";
import { dashboardRoutes } from "./routes/dashboard.routes.js";
import { todoRoutes } from "./routes/todo.routes.js";
import { shiftRoutes } from "./routes/shift.routes.js";
import { streamingRoutes } from "./routes/streaming.routes.js";
import { loadTodos } from "./services/todo-store.js";
import { loadShifts } from "./services/shift-store.js";

loadCommands();
loadTodos();
loadShifts();

const server = Fastify({
  logger: true
});

logConfigWarnings(server.log);

await server.register(cors, {
  origin: false
});

await server.register(websocket);

await server.register(healthRoutes);
await server.register(agentRoutes);
await server.register(newsRoutes);
await server.register(openAiRoutes);
await server.register(commandRoutes);
await server.register(realtimeRoutes);
await server.register(dashboardRoutes);
await server.register(todoRoutes);
await server.register(shiftRoutes);
await server.register(streamingRoutes);

async function start() {
  try {
    await server.listen({
      port: config.port,
      host: config.host
    });

    server.log.info(
      {
        host: config.host,
        port: config.port,
        publicBaseUrl: config.publicBaseUrl
      },
      "JARVIS backend running"
    );
  } catch (error) {
    server.log.error(error);
    process.exit(1);
  }
}

start();
