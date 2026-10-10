/**
 * Enterprise Structured Logging for LangChain & LangGraph (TypeScript / Node.js 24).
 *
 * Emits newline-delimited JSON (NDJSON) with correlation IDs (threadId, runId),
 * automatic PII redaction, token usage metrics, and node execution latencies.
 */

import { BaseCallbackHandler } from "@langchain/core/callbacks/base";
import { Serialized } from "@langchain/core/load/serializable";
import { LLMResult } from "@langchain/core/outputs";
import { BaseMessage } from "@langchain/core/messages";

export interface LogCorrelation {
  runId: string;
  parentRunId?: string | null;
  threadId?: string | null;
}

export interface LogTelemetry {
  durationMs?: number;
  tokens?: {
    promptTokens?: number;
    completionTokens?: number;
    totalTokens?: number;
  };
  modelName?: string;
  toolName?: string;
  nodeName?: string;
  tags?: string[];
  errorType?: string;
}

export interface AgentStructuredLog {
  timestamp: string;
  level: "INFO" | "WARN" | "ERROR";
  logger: string;
  message: string;
  agentEvent:
    | "node.start"
    | "node.end"
    | "llm.start"
    | "llm.end"
    | "llm.error"
    | "tool.start"
    | "tool.end"
    | "tool.error"
    | "chain.error";
  correlation: LogCorrelation;
  telemetry?: LogTelemetry;
  payload?: unknown;
}

export class PIIScrubber {
  private static EMAIL_REGEX = /[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+/g;
  private static API_KEY_REGEX = /(?:api[_-]?key|token|secret|password)["':\s=]+([a-zA-Z0-9_-]{8,})/gi;
  private static PHONE_REGEX = /(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}/g;

  static scrubText(text: unknown): string {
    if (typeof text !== "string") {
      return String(text ?? "");
    }
    return text
      .replace(this.EMAIL_REGEX, "[REDACTED_EMAIL]")
      .replace(this.PHONE_REGEX, "[REDACTED_PHONE]")
      .replace(this.API_KEY_REGEX, 'api_key="[REDACTED_CREDENTIAL]"');
  }

  static scrubData(data: unknown): unknown {
    if (typeof data === "string") {
      return this.scrubText(data);
    }
    if (data === null || typeof data !== "object") {
      return data;
    }
    // LangChain BaseMessage instances
    if ("content" in data && typeof (data as { content: unknown }).content === "string") {
      const msg = data as { _getType?: () => string; content: string; tool_calls?: unknown };
      return {
        type: msg._getType ? msg._getType() : "message",
        content: this.scrubText(msg.content),
        tool_calls: msg.tool_calls ? this.scrubData(msg.tool_calls) : undefined,
      };
    }
    if (Array.isArray(data)) {
      return data.map((item) => this.scrubData(item));
    }
    const record = data as Record<string, unknown>;
    const scrubbed: Record<string, unknown> = {};
    for (const [key, val] of Object.entries(record)) {
      const lowerKey = key.toLowerCase();
      if (["key", "secret", "token", "password"].some((s) => lowerKey.includes(s))) {
        scrubbed[key] = "[REDACTED_CREDENTIAL]";
      } else {
        scrubbed[key] = this.scrubData(val);
      }
    }
    return scrubbed;
  }
}

export class StructuredLogger {
  constructor(private name: string = "telecom.agent.audit") {}

  log(entry: AgentStructuredLog): void {
    const jsonOutput = JSON.stringify(entry);
    if (entry.level === "ERROR") {
      process.stderr.write(jsonOutput + "\n");
    } else {
      process.stdout.write(jsonOutput + "\n");
    }
  }

  info(
    message: string,
    event: AgentStructuredLog["agentEvent"],
    correlation: LogCorrelation,
    telemetry?: LogTelemetry,
    payload?: unknown
  ): void {
    this.log({
      timestamp: new Date().toISOString(),
      level: "INFO",
      logger: this.name,
      message,
      agentEvent: event,
      correlation,
      telemetry,
      payload,
    });
  }

  error(
    message: string,
    event: AgentStructuredLog["agentEvent"],
    correlation: LogCorrelation,
    telemetry?: LogTelemetry,
    payload?: unknown
  ): void {
    this.log({
      timestamp: new Date().toISOString(),
      level: "ERROR",
      logger: this.name,
      message,
      agentEvent: event,
      correlation,
      telemetry,
      payload,
    });
  }
}

export class StructuredLoggingCallbackHandler extends BaseCallbackHandler {
  name = "StructuredLoggingCallbackHandler";
  private startTimes = new Map<string, number>();
  private logger: StructuredLogger;
  public threadId: string | null = null;
  public scrubPii: boolean = true;

  constructor(options?: {
    logger?: StructuredLogger;
    threadId?: string;
    scrubPii?: boolean;
  }) {
    super();
    this.logger = options?.logger ?? new StructuredLogger();
    this.threadId = options?.threadId ?? null;
    this.scrubPii = options?.scrubPii ?? true;
  }

  private getCorrelation(runId: string, parentRunId?: string): LogCorrelation {
    return {
      runId,
      parentRunId: parentRunId ?? null,
      threadId: this.threadId,
    };
  }

  handleChainStart(
    chain: Serialized,
    inputs: Record<string, unknown>,
    runId: string,
    parentRunId?: string,
    tags?: string[],
    metadata?: Record<string, unknown>
  ): void {
    this.startTimes.set(runId, performance.now());
    if (!this.threadId && metadata?.thread_id) {
      this.threadId = String(metadata.thread_id);
    }
    const nodeName =
      (metadata?.langgraph_node as string) ??
      chain.name ??
      (chain.id ? chain.id.at(-1) : "node");

    this.logger.info(
      `Node '${nodeName}' started`,
      "node.start",
      this.getCorrelation(runId, parentRunId),
      { nodeName, tags: tags ?? [] },
      this.scrubPii ? PIIScrubber.scrubData(inputs) : inputs
    );
  }

  handleChainEnd(
    outputs: Record<string, unknown>,
    runId: string,
    parentRunId?: string
  ): void {
    const start = this.startTimes.get(runId) ?? performance.now();
    this.startTimes.delete(runId);
    const durationMs = Number(((performance.now() - start)).toFixed(2));

    this.logger.info(
      `Node completed in ${durationMs}ms`,
      "node.end",
      this.getCorrelation(runId, parentRunId),
      { durationMs },
      this.scrubPii ? PIIScrubber.scrubData(outputs) : outputs
    );
  }

  handleChatModelStart(
    llm: Serialized,
    messages: BaseMessage[][],
    runId: string,
    parentRunId?: string,
    extraParams?: Record<string, unknown>
  ): void {
    this.startTimes.set(runId, performance.now());
    const modelName =
      (extraParams?.invocation_params as Record<string, unknown>)?.model ??
      (extraParams?.invocation_params as Record<string, unknown>)?.model_name ??
      llm.name ??
      "unknown-model";

    const turnCount = messages[0]?.length ?? 0;
    this.logger.info(
      `ChatModel '${modelName}' invoked with ${turnCount} messages`,
      "llm.start",
      this.getCorrelation(runId, parentRunId),
      {
        modelName: String(modelName),
        tags: [turnCount ? `${turnCount}_turns` : "0_turns"],
      }
    );
  }

  handleLLMEnd(
    output: LLMResult,
    runId: string,
    parentRunId?: string
  ): void {
    const start = this.startTimes.get(runId) ?? performance.now();
    this.startTimes.delete(runId);
    const durationMs = Number(((performance.now() - start)).toFixed(2));

    const tokenUsage = output.llmOutput?.tokenUsage ?? {};
    const promptTokens = tokenUsage.promptTokens ?? 0;
    const completionTokens = tokenUsage.completionTokens ?? 0;
    const totalTokens = tokenUsage.totalTokens ?? promptTokens + completionTokens;

    this.logger.info(
      `ChatModel completed in ${durationMs}ms (${totalTokens} tokens)`,
      "llm.end",
      this.getCorrelation(runId, parentRunId),
      {
        durationMs,
        tokens: { promptTokens, completionTokens, totalTokens },
      }
    );
  }

  handleLLMError(
    err: Error,
    runId: string,
    parentRunId?: string
  ): void {
    const start = this.startTimes.get(runId) ?? performance.now();
    this.startTimes.delete(runId);
    const durationMs = Number(((performance.now() - start)).toFixed(2));

    this.logger.error(
      `ChatModel failed: ${err.message}`,
      "llm.error",
      this.getCorrelation(runId, parentRunId),
      { durationMs, errorType: err.name },
      { error: err.message, stack: err.stack }
    );
  }

  handleToolStart(
    tool: Serialized,
    input: unknown,
    runId: string,
    parentRunId?: string
  ): void {
    this.startTimes.set(runId, performance.now());
    const toolName = tool.id?.at(-1) ?? tool.name ?? "tool";

    this.logger.info(
      `Tool '${toolName}' invoked`,
      "tool.start",
      this.getCorrelation(runId, parentRunId),
      { toolName },
      { input: this.scrubPii ? (typeof input === "string" ? PIIScrubber.scrubText(input) : PIIScrubber.scrubData(input)) : input }
    );
  }

  handleToolEnd(
    output: unknown,
    runId: string,
    parentRunId?: string
  ): void {
    const start = this.startTimes.get(runId) ?? performance.now();
    this.startTimes.delete(runId);
    const durationMs = Number(((performance.now() - start)).toFixed(2));

    this.logger.info(
      `Tool execution completed in ${durationMs}ms`,
      "tool.end",
      this.getCorrelation(runId, parentRunId),
      { durationMs },
      { output: this.scrubPii ? (typeof output === "string" ? PIIScrubber.scrubText(output) : PIIScrubber.scrubData(output)) : output }
    );
  }

  handleToolError(
    err: Error,
    runId: string,
    parentRunId?: string
  ): void {
    const start = this.startTimes.get(runId) ?? performance.now();
    this.startTimes.delete(runId);
    const durationMs = Number(((performance.now() - start)).toFixed(2));

    this.logger.error(
      `Tool failed: ${err.message}`,
      "tool.error",
      this.getCorrelation(runId, parentRunId),
      { durationMs, errorType: err.name },
      { error: err.message, stack: err.stack }
    );
  }
}

