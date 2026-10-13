/**
 * Standalone Express SSE Agent Server (Pattern B: Decoupled Agent Microservice).
 *
 * Runs the LangGraph tool-calling agent in an independent Node.js process,
 * streaming lifecycle events over Server-Sent Events (SSE) to remote consumers.
 */

import cors from "cors";
import express, { Request, Response } from "express";
import { getConfiguredProviders, loadWorkspaceEnv, validateProviderKey } from "../../core/env.js";
import { createAgent, streamAgentLifecycle, toBaseMessages } from "../core/agent.js";
import { ChatRequest } from "../core/types.js";
import { globalToolRegistry } from "../tools/registry.js";

// Ensure environment variables from python/.env or root .env are loaded
loadWorkspaceEnv();

const PORT = parseInt(process.env.AGENT_PORT || process.env.PORT || "4000", 10);
const app = express();

app.use(cors());
app.use(express.json());

// Maintain cached agents by (provider, model)
const agentCache = new Map<string, ReturnType<typeof createAgent>>();

function getOrCreateAgent(provider: string = "mock", model?: string) {
  validateProviderKey(provider);
  const key = `${provider.toLowerCase()}:${model ?? "default"}`;
  if (!agentCache.has(key)) {
    agentCache.set(key, createAgent({ provider: provider as any, model }));
  }
  return agentCache.get(key)!;
}

/**
 * Health check endpoint.
 */
app.get("/health", (_req: Request, res: Response) => {
  res.json({
    status: "healthy",
    service: "agent-microservice",
    runtime: "Node.js (TypeScript)",
    port: PORT,
    timestamp: new Date().toISOString(),
    configured_providers: getConfiguredProviders(),
    configuredProviders: getConfiguredProviders(),
  });
});

/**
 * Tool inventory endpoint.
 */
app.get("/tools", (_req: Request, res: Response) => {
  res.json({
    tools: globalToolRegistry.getSchemas(),
  });
});

/**
 * SSE Chat Stream Endpoint (Pattern B).
 * Streams normalized lifecycle events: token, tool_start, tool_end, done, error.
 */
app.post("/agent/chat/stream", async (req: Request, res: Response) => {
  const body: ChatRequest = req.body || {};
  const { prompt, messages, provider = "mock", model, threadId = "default-session" } = body;

  let inputMessages: ReturnType<typeof toBaseMessages>;
  if (messages && messages.length > 0) {
    inputMessages = toBaseMessages(messages);
  } else if (prompt) {
    inputMessages = toBaseMessages(prompt);
  } else {
    res.status(400).json({ error: "Missing 'prompt' or 'messages' in request body." });
    return;
  }

  // Set SSE streaming headers
  res.setHeader("Content-Type", "text/event-stream");
  res.setHeader("Cache-Control", "no-cache, no-transform");
  res.setHeader("Connection", "keep-alive");
  res.setHeader("X-Accel-Buffering", "no");
  res.flushHeaders?.();

  let clientAborted = false;
  res.on("close", () => {
    if (!res.writableEnded) {
      clientAborted = true;
    }
  });

  try {
    const agent = getOrCreateAgent(provider, model);
    const stream = streamAgentLifecycle(agent, inputMessages, threadId);

    for await (const event of stream) {
      if (clientAborted) break;
      res.write(`data: ${JSON.stringify(event)}\n\n`);
    }
  } catch (err: any) {
    if (!clientAborted && !res.writableEnded) {
      res.write(`data: ${JSON.stringify({ event: "error", error: err?.message ?? String(err) })}\n\n`);
    }
  } finally {
    if (!res.writableEnded) {
      res.end();
    }
  }
});

export function startAgentServer(port: number = PORT) {
  return app.listen(port, () => {
    console.log(`[Agent Microservice] Running on http://localhost:${port}`);
    console.log(`[Agent Microservice] SSE endpoint: POST http://localhost:${port}/agent/chat/stream`);
  });
}

// Auto-run if executed directly
if (process.argv[1] && process.argv[1].endsWith("agentServer.ts")) {
  startAgentServer();
}

export { app };
