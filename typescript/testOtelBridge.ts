import test from "node:test";
import assert from "node:assert/strict";
import { HumanMessage, AIMessage } from "@langchain/core/messages";
import { LLMResult } from "@langchain/core/outputs";
import {
  OpenTelemetryGenAICallbackHandler,
  OpenTelemetrySpan,
  generateTraceId,
  generateSpanId,
} from "./src/langchain_suite/core/otelBridge.js";

test("generateTraceId and generateSpanId generate compliant hex strings", () => {
  const traceId = generateTraceId();
  const spanId = generateSpanId();

  assert.equal(traceId.length, 32);
  assert.equal(spanId.length, 16);
  assert.ok(/^[0-9a-f]{32}$/.test(traceId));
  assert.ok(/^[0-9a-f]{16}$/.test(spanId));
});

test("OpenTelemetrySpan records lifecycle, status, and duration", () => {
  const span = new OpenTelemetrySpan({
    name: "test.op",
    traceId: generateTraceId(),
    spanId: generateSpanId(),
  });

  assert.equal(span.statusCode, "UNSET");
  assert.equal(span.endTimeNs, undefined);

  span.finish("OK");
  assert.equal(span.statusCode, "OK");
  assert.ok(span.endTimeNs !== undefined);
  assert.ok(span.durationMs >= 0);
});

test("OpenTelemetryGenAICallbackHandler captures chat model events, tokens, and scrubs PII", async () => {
  const exportedSpans: OpenTelemetrySpan[] = [];
  const handler = new OpenTelemetryGenAICallbackHandler({
    serviceName: "telekom-ts-agent",
    threadId: "session-xyz-99",
    scrubPii: true,
    spanExporter: (span) => exportedSpans.push(span),
  });

  const runId = "test-run-001";
  const messages = [[new HumanMessage("Contact support at customer@telekom.com")]];

  await handler.handleChatModelStart(
    { name: "ChatOpenAI", id: ["chat", "openai"] },
    messages,
    runId,
    undefined,
    { metadata: { model_name: "gpt-4o" } }
  );

  const mockLlmResult: LLMResult = {
    generations: [[{ text: "Assisting customer now.", message: new AIMessage("Assisting customer now.") }]],
    llmOutput: {
      tokenUsage: {
        promptTokens: 25,
        completionTokens: 12,
        totalTokens: 37,
      },
    },
  };

  await handler.handleLLMEnd(mockLlmResult, runId);

  assert.equal(exportedSpans.length, 1);
  const span = exportedSpans[0];

  assert.equal(span.name, "gen_ai.chat gpt-4o");
  assert.equal(span.attributes["gen_ai.system"], "openai");
  assert.equal(span.attributes["gen_ai.request.model"], "gpt-4o");
  assert.equal(span.attributes["gen_ai.operation.name"], "chat");
  assert.equal(span.attributes["gen_ai.usage.prompt_tokens"], 25);
  assert.equal(span.attributes["gen_ai.usage.completion_tokens"], 12);
  assert.equal(span.attributes["gen_ai.usage.total_tokens"], 37);
  assert.equal(span.attributes["session.id"], "session-xyz-99");

  // PII Scrubbing check
  assert.ok(String(span.attributes["gen_ai.prompt"]).includes("[REDACTED_EMAIL]"));
  assert.ok(!String(span.attributes["gen_ai.prompt"]).includes("customer@telekom.com"));
});

test("OpenTelemetryGenAICallbackHandler tracks tool executions and parent-child span nesting", async () => {
  const handler = new OpenTelemetryGenAICallbackHandler({ serviceName: "telekom-ts-agent" });

  const chainRunId = "chain-001";
  await handler.handleChainStart({ id: ["AgentWorkflow"] }, { query: "check" }, chainRunId);

  const toolRunId = "tool-001";
  await handler.handleToolStart({ id: ["fetch_sim_status"] }, "imsi=1234567890", toolRunId);
  await handler.handleToolEnd({ status: "ACTIVE" }, toolRunId);
  await handler.handleChainEnd({ result: "done" }, chainRunId);

  assert.equal(handler.completedSpans.length, 2);
  const toolSpan = handler.completedSpans[0];
  const chainSpan = handler.completedSpans[1];

  assert.equal(toolSpan.name, "gen_ai.tool fetch_sim_status");
  assert.equal(toolSpan.attributes["gen_ai.operation.name"], "execute_tool");
  assert.equal(toolSpan.parentSpanId, chainSpan.spanId);

  // OTLP export format check
  const otlp = handler.exportOtlpPayload();
  assert.ok(Array.isArray((otlp as any).resourceSpans));
  assert.equal((otlp as any).resourceSpans[0].resource.attributes[0].key, "service.name");
});

test("OpenTelemetryGenAICallbackHandler records errors with exception events", async () => {
  const handler = new OpenTelemetryGenAICallbackHandler({ serviceName: "telekom-ts-agent" });
  const runId = "error-run-001";

  await handler.handleChatModelStart(
    { name: "ChatAnthropic", id: ["chat", "claude"] },
    [[new HumanMessage("Test")]],
    runId,
    undefined,
    { metadata: { model_name: "claude-3-5-sonnet" } }
  );

  await handler.handleLLMError(new Error("RateLimit 429"), runId);

  assert.equal(handler.completedSpans.length, 1);
  const span = handler.completedSpans[0];
  assert.equal(span.statusCode, "ERROR");
  assert.equal(span.statusMessage, "RateLimit 429");
  assert.equal(span.events.length, 1);
  assert.equal(span.events[0].name, "exception");
});

