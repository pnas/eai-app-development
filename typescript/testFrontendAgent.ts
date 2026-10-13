import test from "node:test";
import assert from "node:assert/strict";
import http from "node:http";
import { getCurrentTime, getRandomQuote } from "./src/langchain_suite/frontend_agent/tools/defaultTools.js";
import { ToolRegistry, globalToolRegistry } from "./src/langchain_suite/frontend_agent/tools/registry.js";
import { MockAgentChatModel } from "./src/langchain_suite/frontend_agent/core/mockModel.js";
import { createAgent, streamAgentLifecycle, toBaseMessages } from "./src/langchain_suite/frontend_agent/core/agent.js";
import { app as backendApp } from "./src/langchain_suite/frontend_agent/backend/agentServer.js";
import { app as webApp } from "./src/langchain_suite/frontend_agent/webApp/server.js";

test("Tools: getCurrentTime formats valid and handles fallback timezones", async () => {
  const berlinTime = await getCurrentTime.invoke({ timezone: "Europe/Berlin" });
  assert.ok(berlinTime.includes("Europe/Berlin"));
  assert.ok(berlinTime.includes("ISO:"));

  const tokyoTime = await getCurrentTime.invoke({ timezone: "Asia/Tokyo" });
  assert.ok(tokyoTime.includes("Asia/Tokyo"));

  const fallbackTime = await getCurrentTime.invoke({ timezone: "Invalid/Timezone" });
  assert.ok(fallbackTime.includes("defaulted to UTC"));
});

test("Tools: getRandomQuote returns quotes by category", async () => {
  const techQuote = await getRandomQuote.invoke({ category: "technology" });
  assert.ok(techQuote.includes("[Technology]"));

  const philoQuote = await getRandomQuote.invoke({ category: "philosophy" });
  assert.ok(philoQuote.includes("[Philosophy]"));

  const allQuote = await getRandomQuote.invoke({ category: "all" });
  assert.ok(allQuote.length > 10);
});

test("ToolRegistry registers, retrieves, and exports JSON schema", () => {
  const registry = new ToolRegistry();
  registry.register(getCurrentTime);
  registry.register(getRandomQuote);

  assert.equal(registry.getAll().length, 2);
  assert.ok(registry.get("get_current_time"));
  assert.ok(registry.get("get_random_quote"));

  const schemas = registry.getSchemas();
  assert.equal(schemas.length, 2);
  assert.equal(schemas[0].name, "get_current_time");
  assert.ok(schemas[0].schema);
});

test("MockAgentChatModel triggers time and quote tool calls and streams tokens", async () => {
  const mock = new MockAgentChatModel();

  // Test conversation
  const convRes = await mock.invoke(toBaseMessages("Hello"));
  assert.ok(String(convRes.content).includes("Hello! I am your AI assistant"));

  // Test time tool trigger
  const timeRes = await mock.invoke(toBaseMessages("What time is it in Tokyo?"));
  assert.equal(timeRes.tool_calls?.length, 1);
  assert.equal(timeRes.tool_calls?.[0].name, "get_current_time");
  assert.deepEqual(timeRes.tool_calls?.[0].args, { timezone: "Asia/Tokyo" });

  // Test quote tool trigger
  const quoteRes = await mock.invoke(toBaseMessages("Give me a motivational quote"));
  assert.equal(quoteRes.tool_calls?.length, 1);
  assert.equal(quoteRes.tool_calls?.[0].name, "get_random_quote");
  assert.deepEqual(quoteRes.tool_calls?.[0].args, { category: "motivation" });
});

test("LangGraph Agent + streamAgentLifecycle produces normalized lifecycle events", async () => {
  const agent = createAgent({ provider: "mock" });
  const events: any[] = [];

  const messages = toBaseMessages("What time is it in Berlin?");
  for await (const evt of streamAgentLifecycle(agent, messages, "test-stream-thread")) {
    events.push(evt);
  }

  // Should have tool_start, tool_end, tokens, and done
  const toolStart = events.find((e) => e.event === "tool_start");
  const toolEnd = events.find((e) => e.event === "tool_end");
  const tokens = events.filter((e) => e.event === "token");
  const done = events.find((e) => e.event === "done");

  assert.ok(toolStart, "Should have received tool_start event");
  assert.equal(toolStart.tool, "get_current_time");
  assert.equal(toolStart.input.timezone, "Europe/Berlin");

  assert.ok(toolEnd, "Should have received tool_end event");
  assert.equal(toolEnd.tool, "get_current_time");
  assert.ok(toolEnd.output.includes("Europe/Berlin"));

  assert.ok(tokens.length > 0, "Should have received streaming tokens");
  assert.ok(done, "Should have received done event");
  assert.equal(done.status, "completed");
});

test("Backend Server (Pattern B) and Web App (Pattern A & B) HTTP/SSE Integration", async () => {
  // 1. Start Backend on dynamic port
  const backendServer = http.createServer(backendApp);
  await new Promise<void>((resolve) => backendServer.listen(0, resolve));
  const backendPort = (backendServer.address() as any).port;
  const backendBase = `http://127.0.0.1:${backendPort}`;

  // 2. Start Web Server on dynamic port
  const webServer = http.createServer(webApp);
  await new Promise<void>((resolve) => webServer.listen(0, resolve));
  const webPort = (webServer.address() as any).port;
  const webBase = `http://127.0.0.1:${webPort}`;

  try {
    // Health check on backend
    const backendHealth = await fetch(`${backendBase}/health`).then((r) => r.json());
    assert.equal(backendHealth.status, "healthy");
    assert.equal(backendHealth.service, "agent-microservice");
    assert.ok(backendHealth.configured_providers, "Health response should contain configured_providers");
    assert.equal(typeof backendHealth.configured_providers.openai, "boolean");
    assert.equal(typeof backendHealth.configured_providers.anthropic, "boolean");

    // Tools list on backend
    const backendTools = await fetch(`${backendBase}/tools`).then((r) => r.json());
    assert.equal(backendTools.tools.length, 2);

    // Pattern B Direct: SSE Chat Stream on Backend
    const backendStreamRes = await fetch(`${backendBase}/agent/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt: "What time is it in London?", provider: "mock" }),
    });
    assert.equal(backendStreamRes.status, 200);
    assert.ok(backendStreamRes.headers.get("content-type")?.includes("text/event-stream"));
    const backendStreamText = await backendStreamRes.text();
    assert.ok(backendStreamText.includes('"event":"tool_start"'));
    assert.ok(backendStreamText.includes('"event":"tool_end"'));
    assert.ok(backendStreamText.includes('"event":"done"'));

    // Pattern A: In-Process Chat Stream on Web App
    const inProcRes = await fetch(`${webBase}/api/chat/in-process`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt: "Give me an inspirational tech quote", provider: "mock" }),
    });
    assert.equal(inProcRes.status, 200);
    assert.ok(inProcRes.headers.get("content-type")?.includes("text/event-stream"));
    const inProcText = await inProcRes.text();
    assert.ok(inProcText.includes('"event":"tool_start"'));
    assert.ok(inProcText.includes('get_random_quote'));
    assert.ok(inProcText.includes('"event":"done"'));

    // Pattern B: Remote Proxy via Web App
    const remoteProxyRes = await fetch(`${webBase}/api/chat/remote`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        prompt: "Hello assistant!",
        provider: "mock",
        remoteUrl: `${backendBase}/agent/chat/stream`,
      }),
    });
    assert.equal(remoteProxyRes.status, 200);
    assert.ok(remoteProxyRes.headers.get("content-type")?.includes("text/event-stream"));
    const proxyText = await remoteProxyRes.text();
    assert.ok(proxyText.includes('"event":"token"'));
    assert.ok(proxyText.includes('"event":"done"'));
  } finally {
    await new Promise<void>((resolve) => backendServer.close(() => resolve()));
    await new Promise<void>((resolve) => webServer.close(() => resolve()));
  }
});
