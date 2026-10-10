import test from "node:test";
import assert from "node:assert/strict";
import { AIMessage, HumanMessage } from "@langchain/core/messages";
import { LLMResult } from "@langchain/core/outputs";
import {
  PIIScrubber,
  StructuredLogger,
  StructuredLoggingCallbackHandler,
  AgentStructuredLog,
} from "./src/langchain_suite/core/structuredLogger.js";

test("PIIScrubber redacts sensitive patterns in text", () => {
  const rawText =
    "Subscriber email is alice@telekom.de, phone +49 170 5551234, api_key='secret-auth-key-123'";
  const scrubbed = PIIScrubber.scrubText(rawText);

  assert.ok(scrubbed.includes("[REDACTED_EMAIL]"));
  assert.ok(scrubbed.includes("[REDACTED_PHONE]"));
  assert.ok(scrubbed.includes("[REDACTED_CREDENTIAL]"));
  assert.ok(!scrubbed.includes("alice@telekom.de"));
  assert.ok(!scrubbed.includes("+49 170 5551234"));
  assert.ok(!scrubbed.includes("secret-auth-key-123"));
});

test("PIIScrubber redacts nested objects and message structures", () => {
  const input = {
    userEmail: "ops@company.com",
    apiKey: "prod-secret-9999",
    meta: {
      password: "pass",
      contact: "Call 555-019-2834 now",
    },
  };

  const scrubbed = PIIScrubber.scrubData(input) as Record<string, any>;
  assert.equal(scrubbed.userEmail, "[REDACTED_EMAIL]");
  assert.equal(scrubbed.apiKey, "[REDACTED_CREDENTIAL]");
  assert.equal(scrubbed.meta.password, "[REDACTED_CREDENTIAL]");
  assert.ok(scrubbed.meta.contact.includes("[REDACTED_PHONE]"));

  const aiMsg = new AIMessage("User phone: 212-555-0144");
  const scrubbedMsg = PIIScrubber.scrubData(aiMsg) as Record<string, any>;
  assert.ok(scrubbedMsg.content.includes("[REDACTED_PHONE]"));
});

test("StructuredLoggingCallbackHandler captures chat model lifecycle and tokens", () => {
  const capturedLogs: AgentStructuredLog[] = [];
  const mockLogger = new StructuredLogger("test.audit");
  mockLogger.log = (entry: AgentStructuredLog) => {
    capturedLogs.push(entry);
  };

  const handler = new StructuredLoggingCallbackHandler({
    logger: mockLogger,
    threadId: "test-thread-ts-01",
  });

  // 1. handleChatModelStart
  handler.handleChatModelStart(
    { name: "ChatAnthropic", id: ["chat", "anthropic"] },
    [[new HumanMessage("Test prompt")]],
    "run-ts-1",
    undefined,
    { invocation_params: { model: "claude-3-5-haiku" } }
  );

  assert.equal(capturedLogs.length, 1);
  const startLog = capturedLogs[0];
  assert.equal(startLog.agentEvent, "llm.start");
  assert.equal(startLog.correlation.threadId, "test-thread-ts-01");
  assert.equal(startLog.correlation.runId, "run-ts-1");
  assert.equal(startLog.telemetry?.modelName, "claude-3-5-haiku");

  // 2. handleLLMEnd
  const llmResult: LLMResult = {
    generations: [[{ text: "Response" }]],
    llmOutput: {
      tokenUsage: { promptTokens: 40, completionTokens: 15, totalTokens: 55 },
    },
  };
  handler.handleLLMEnd(llmResult, "run-ts-1");

  assert.equal(capturedLogs.length, 2);
  const endLog = capturedLogs[1];
  assert.equal(endLog.agentEvent, "llm.end");
  assert.equal(endLog.telemetry?.tokens?.totalTokens, 55);
  assert.ok(typeof endLog.telemetry?.durationMs === "number");
});

test("StructuredLoggingCallbackHandler captures tool execution and error handling", () => {
  const capturedLogs: AgentStructuredLog[] = [];
  const mockLogger = new StructuredLogger("test.audit");
  mockLogger.log = (entry: AgentStructuredLog) => {
    capturedLogs.push(entry);
  };

  const handler = new StructuredLoggingCallbackHandler({
    logger: mockLogger,
    threadId: "test-thread-ts-02",
  });

  // handleToolStart
  handler.handleToolStart(
    { name: "lookup_account", id: ["tools", "lookup_account"] },
    "query user email=john@telekom.com",
    "tool-ts-1"
  );

  assert.equal(capturedLogs.length, 1);
  const toolStart = capturedLogs[0];
  assert.equal(toolStart.agentEvent, "tool.start");
  const payload = toolStart.payload as { input: string };
  assert.ok(payload.input.includes("[REDACTED_EMAIL]"));

  // handleToolError
  handler.handleToolError(new Error("Database timeout"), "tool-ts-1");
  assert.equal(capturedLogs.length, 2);
  const toolError = capturedLogs[1];
  assert.equal(toolError.agentEvent, "tool.error");
  assert.equal(toolError.level, "ERROR");
  assert.equal(toolError.telemetry?.errorType, "Error");
});

