/**
 * Convenience Launcher for the TypeScript Web Application & Agent Microservice Showcase.
 *
 * Usage:
 *     # Run Web Application UI (Pattern A & B host on port 3000):
 *     npm run start:frontend:webapp
 *
 *     # Run Standalone Agent Microservice (Pattern B SSE on port 4000):
 *     npm run start:frontend:backend
 *
 *     # Run Both Services Simultaneously:
 *     npm run start:frontend:all
 */

import { startAgentServer } from "./backend/agentServer.js";
import { startWebServer } from "./webApp/server.js";

const args = process.argv.slice(2);
const runAll = args.includes("--all") || args.length === 0;
const runBackendOnly = args.includes("--backend");
const runWebOnly = args.includes("--webapp") || args.includes("--frontend");

const BACKEND_PORT = parseInt(process.env.AGENT_PORT || "4000", 10);
const WEB_PORT = parseInt(process.env.WEB_PORT || "3000", 10);

console.log("===============================================================================");
console.log(" 🌐 LangGraph Agent Architecture Showcase (TypeScript / Node.js 24) ");
console.log("===============================================================================\n");

if (runBackendOnly) {
  startAgentServer(BACKEND_PORT);
} else if (runWebOnly) {
  startWebServer(WEB_PORT);
} else if (runAll) {
  console.log("Launching Dual-Mode Architecture Demonstration:");
  console.log(" • Pattern A: In-Process Monolith host directly on Web App (Port 3000)");
  console.log(" • Pattern B: Decoupled Agent Microservice on Port 4000\n");

  const backendServer = startAgentServer(BACKEND_PORT);
  const webServer = startWebServer(WEB_PORT);

  console.log("\n🚀 Open your browser at: http://localhost:3000");
  console.log("   Press Ctrl+C to stop both servers.\n");

  const shutdown = () => {
    console.log("\n🛑 Gracefully shutting down servers...");
    backendServer.close(() => console.log("✔ Agent Microservice stopped."));
    webServer.close(() => console.log("✔ Web Application stopped."));
    process.exit(0);
  };

  process.on("SIGINT", shutdown);
  process.on("SIGTERM", shutdown);
}

