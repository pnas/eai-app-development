/**
 * Web Application Server (Dual Pattern Integration Host).
 *
 * Demonstrates:
 * 1. Pattern A: In-Process Monolith - agent executed directly in this Node.js process.
 * 2. Pattern B: Decoupled Agent Microservice - proxies/streams from an independent SSE backend.
 *
 * Also serves the responsive Single-Page Chat UI from the public/ directory.
 */

import cors from "cors";
import express, { Request, Response } from "express";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { loadWorkspaceEnv } from "../../core/env.js";
import { createAgent, streamAgentLifecycle, toBaseMessages } from "../core/agent.js";
import { ChatRequest } from "../core/types.js";
import { globalToolRegistry } from "../tools/registry.js";

loadWorkspaceEnv();

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const WEB_PORT = parseInt(process.env.WEB_PORT || process.env.PORT || "3000", 10);
const DEFAULT_REMOTE_BACKEND = process.env.REMOTE_AGENT_URL || "http://localhost:4000/agent/chat/stream";

const app = express();

app.use(cors());
app.use(express.json());

// Serve static frontend assets
const publicDir = path.join(__dirname, "public");
app.use(express.static(publicDir));

// In-process agent cache
const inProcessAgentCache = new Map<string, ReturnType<typeof createAgent>>();

function getOrCreateInProcessAgent(provider: string = "mock", model?: string) {
  const key = `${provider.toLowerCase()}:${model ?? "default"}`;
  if (!inProcessAgentCache.has(key)) {
    inProcessAgentCache.set(key, createAgent({ provider: provider as any, model }));
  }
  return inProcessAgentCache.get(key)!;
}

/**
 * Health check endpoint.
 */
app.get("/api/health", (_req: Request, res: Response) => {
  res.json({
    status: "healthy",
    service: "web-app-host",
    runtime: "Node.js (TypeScript)",
    port: WEB_PORT,
    defaultRemoteBackend: DEFAULT_REMOTE_BACKEND,
    timestamp: new Date().toISOString(),
  });
});

/**
 * Tool registry metadata for frontend inspection.
 */
app.get("/api/tools", (_req: Request, res: Response) => {
  res.json({
    tools: globalToolRegistry.getSchemas(),
  });
});

/**
 * PATTERN A: In-Process Monolith Endpoint.
 * Executes the LangGraph agent in the current Node.js process and streams SSE directly.
 */
app.post("/api/chat/in-process", async (req: Request, res: Response) => {
  const body: ChatRequest = req.body || {};
  const { prompt, messages, provider = "mock", model, threadId = "in-proc-session" } = body;

  let inputMessages: ReturnType<typeof toBaseMessages>;
  if (messages && messages.length > 0) {
    inputMessages = toBaseMessages(messages);
  } else if (prompt) {
    inputMessages = toBaseMessages(prompt);
  } else {
    res.status(400).json({ error: "Missing 'prompt' or 'messages' in request body." });
    return;
  }

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
    const agent = getOrCreateInProcessAgent(provider, model);
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

/**
 * PATTERN B: Decoupled Agent Microservice Proxy Endpoint.
 * Streams chat events from an external remote SSE backend (TypeScript or Python).
 */
app.post("/api/chat/remote", async (req: Request, res: Response) => {
  const body = req.body || {};
  const remoteUrl = body.remoteUrl || DEFAULT_REMOTE_BACKEND;

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
    const upstreamResponse = await fetch(remoteUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
      },
      body: JSON.stringify({
        prompt: body.prompt,
        messages: body.messages,
        provider: body.provider ?? "mock",
        model: body.model,
        threadId: body.threadId ?? "remote-session",
      }),
    });

    if (!upstreamResponse.ok) {
      const errText = await upstreamResponse.text().catch(() => "");
      const errorMsg = `Remote microservice returned status ${upstreamResponse.status}: ${errText}`;
      res.write(`data: ${JSON.stringify({ event: "error", error: errorMsg })}\n\n`);
      res.end();
      return;
    }

    if (!upstreamResponse.body) {
      res.write(`data: ${JSON.stringify({ event: "error", error: "Remote backend returned no response body stream." })}\n\n`);
      res.end();
      return;
    }

    const reader = upstreamResponse.body.getReader();
    const decoder = new TextDecoder("utf-8");

    while (!clientAborted) {
      const { done, value } = await reader.read();
      if (done) break;
      const chunk = decoder.decode(value, { stream: true });
      res.write(chunk);
    }
  } catch (err: any) {
    if (!clientAborted && !res.writableEnded) {
      const errorMsg = `Failed to connect to remote agent microservice at ${remoteUrl}: ${err?.message ?? String(err)}. Ensure the backend process is running.`;
      res.write(`data: ${JSON.stringify({ event: "error", error: errorMsg })}\n\n`);
    }
  } finally {
    if (!res.writableEnded) {
      res.end();
    }
  }
});

// Fallback route for SPA
app.use((_req: Request, res: Response) => {
  res.sendFile(path.join(publicDir, "index.html"));
});

export function startWebServer(port: number = WEB_PORT) {
  return app.listen(port, () => {
    console.log(`[Web App] Running on http://localhost:${port}`);
    console.log(`[Web App] Pattern A (In-Process): POST http://localhost:${port}/api/chat/in-process`);
    console.log(`[Web App] Pattern B (Remote SSE):  POST http://localhost:${port}/api/chat/remote -> ${DEFAULT_REMOTE_BACKEND}`);
  });
}

// Auto-run if executed directly
if (process.argv[1] && process.argv[1].endsWith("server.ts")) {
  startWebServer();
}

export { app };
