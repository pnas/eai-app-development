/**
 * Dual-Telemetry Demonstration (TypeScript / Node.js 24).
 *
 * Demonstrates:
 * 1. Configuring LangSmith distributed tracing via environment variables.
 * 2. Concurrently attaching StructuredLoggingCallbackHandler for in-band JSON logs.
 * 3. Capturing agent internals: state transitions, tool payloads, latencies, tokens.
 * 4. Automatic PII scrubbing (phone numbers, emails, API keys).
 * 5. Correlation tracking via threadId and runId.
 */

import { BaseChatModel } from "@langchain/core/language_models/chat_models";
import {
  AIMessage,
  BaseMessage,
  HumanMessage,
  ToolMessage,
} from "@langchain/core/messages";
import { ChatResult } from "@langchain/core/outputs";
import { Annotation, StateGraph, START } from "@langchain/langgraph";
import { ToolNode, toolsCondition } from "@langchain/langgraph/prebuilt";
import pc from "picocolors";

import {
  StructuredLoggingCallbackHandler,
  StructuredLogger,
} from "../core/structuredLogger.js";
import { agentTools } from "./tools.js";

/**
 * Deterministic Mock ChatModel that simulates tool calling and token usage.
 */
class MockTelecomChatModel extends BaseChatModel {
  _llmType() {
    return "mock-telecom-chat-ts";
  }

  bindTools(_tools: unknown[]) {
    return this;
  }

  async _generate(
    messages: BaseMessage[],
    _options: unknown
  ): Promise<ChatResult> {
    const hasToolResult = messages.some(
      (m) => m instanceof ToolMessage || (m as { _getType?: () => string })._getType?.() === "tool"
    );

    if (!hasToolResult) {
      return {
        generations: [
          {
            text: "",
            message: new AIMessage({
              content: "",
              tool_calls: [
                {
                  name: "lookup_telecom_account",
                  args: { accountId: "ACCT-1001" },
                  id: "call_ts_audit_01",
                  type: "tool_call",
                },
              ],
            }),
          },
        ],
        llmOutput: {
          tokenUsage: {
            promptTokens: 135,
            completionTokens: 28,
            totalTokens: 163,
          },
        },
      };
    } else {
      return {
        generations: [
          {
            text: "Account ACCT-1001 verified. Subscriber Acme Logistics GmbH is on Enterprise 5G with healthy balance.",
            message: new AIMessage({
              content:
                "Account ACCT-1001 verified. Subscriber Acme Logistics GmbH is on Enterprise 5G with healthy balance.",
            }),
          },
        ],
        llmOutput: {
          tokenUsage: {
            promptTokens: 215,
            completionTokens: 38,
            totalTokens: 253,
          },
        },
      };
    }
  }
}

const AgentState = Annotation.Root({
  messages: Annotation<BaseMessage[]>({
    reducer: (x, y) => x.concat(y),
    default: () => [],
  }),
});

export async function runDualTelemetryDemo(): Promise<void> {
  console.log(pc.yellow("\n==========================================================="));
  console.log(pc.yellow(" Dual-Telemetry: LangSmith Tracing & Structured Logging (TS)"));
  console.log(pc.yellow("===========================================================\n"));

  // 1. Inspect LangSmith Environment Configuration
  const langsmithTracing = process.env.LANGCHAIN_TRACING_V2 === "true";
  const langsmithProject = process.env.LANGCHAIN_PROJECT ?? "telekom-default-project";
  const langsmithApiKey = process.env.LANGCHAIN_API_KEY;

  console.log(pc.cyan("┌── 1. LangSmith Tracing Configuration ───────────────────────┐"));
  console.log(pc.cyan(`│ • LANGCHAIN_TRACING_V2: ${langsmithTracing ? pc.green("true") : pc.gray("false")}`));
  console.log(pc.cyan(`│ • LANGCHAIN_PROJECT:    ${langsmithProject}`));
  console.log(
    pc.cyan(
      `│ • LANGCHAIN_API_KEY:    ${
        langsmithApiKey ? pc.green("Configured (Active)") : pc.yellow("Not set (Local logging mode)")
      }`
    )
  );
  console.log(pc.cyan("└─────────────────────────────────────────────────────────────┘\n"));

  // 2. Configure Enterprise Structured Logger & Callback Handler
  const threadId = "session-audit-ts-8842";
  const structuredLogger = new StructuredLogger("telecom.agent.audit");
  const callbackHandler = new StructuredLoggingCallbackHandler({
    logger: structuredLogger,
    threadId,
    scrubPii: true,
  });

  console.log(pc.green("┌── 2. In-Band Structured Logging Configuration ──────────────┐"));
  console.log(pc.green(`│ • Correlation threadId: ${pc.bold(threadId)}`));
  console.log(pc.green("│ • Format:               NDJSON (Newline-Delimited JSON)"));
  console.log(pc.green("│ • Ingestion Target:     stdout -> Vector/Fluentbit -> Splunk/Datadog"));
  console.log(pc.green("│ • PII Sanitization:     Enabled (scrubs emails, phones, API keys)"));
  console.log(pc.green("└─────────────────────────────────────────────────────────────┘\n"));

  // 3. Assemble LangGraph Agent
  const model = new MockTelecomChatModel({});
  const toolNode = new ToolNode(agentTools);

  async function agentNode(state: typeof AgentState.State) {
    const response = await model.invoke(state.messages);
    return { messages: [response] };
  }

  const workflow = new StateGraph(AgentState)
    .addNode("agent", agentNode)
    .addNode("tools", toolNode)
    .addEdge(START, "agent")
    .addConditionalEdges("agent", toolsCondition)
    .addEdge("tools", "agent");

  const graph = workflow.compile();

  console.log(pc.cyan("3. Executing Agent Workflow with Dual Telemetry Attached...\n"));
  console.log(pc.gray("--- Structured JSON Log Stream (Simulating SIEM output) ---"));

  // Invoke with dual telemetry
  const result = await graph.invoke(
    {
      messages: [
        new HumanMessage("Please investigate account ACCT-1001 for cellular issues."),
      ],
    },
    {
      callbacks: [callbackHandler],
      configurable: { thread_id: threadId },
      metadata: { thread_id: threadId, customer_tier: "enterprise" },
    }
  );

  console.log(pc.gray("-------------------------------------------------------------\n"));

  // 4. Summary Verification
  const lastMsg = result.messages.at(-1);
  console.log(pc.green("┌── [OK] Execution Succeeded ────────────────────────────────┐"));
  console.log(pc.green(`│ Final Response: ${lastMsg?.content ?? ""}`));
  console.log(pc.green("│"));
  console.log(pc.green("│ Tracing & Logging Verification:"));
  console.log(pc.green("│ 1. LangSmith receives root graph run, tool child spans, and token metadata."));
  console.log(pc.green(`│ 2. Local logger emitted structured JSON with correlation ID '${threadId}'.`));
  console.log(pc.green("│ 3. Sensitive phone numbers in tool response were scrubbed before output."));
  console.log(pc.green("└─────────────────────────────────────────────────────────────┘\n"));
}

if (process.argv[1]?.includes("dualTelemetryDemo")) {
  runDualTelemetryDemo().catch((err) => {
    console.error("Dual telemetry demo error:", err);
    process.exit(1);
  });
}
