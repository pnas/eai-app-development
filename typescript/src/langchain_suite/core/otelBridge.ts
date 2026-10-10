/**
 * OpenTelemetry GenAI Semantic Conventions Bridge for LangChain & LangGraph (TypeScript / Node.js 24).
 *
 * Implements an OpenTelemetry-compliant callback handler that captures LLM, tool,
 * and chain executions conforming to the official OpenTelemetry GenAI Semantic Conventions:
 * - gen_ai.system (e.g. 'openai', 'anthropic', 'gemini')
 * - gen_ai.request.model
 * - gen_ai.operation.name ('chat', 'execute_tool', 'workflow_step')
 * - gen_ai.usage.prompt_tokens
 * - gen_ai.usage.completion_tokens
 * - gen_ai.usage.total_tokens
 *
 * Emits standard OpenTelemetry Trace & Span structures exportable to any OTel Collector
 * or APM platform (Jaeger, Datadog, Dynatrace, Google Cloud Trace).
 */

import crypto from "node:crypto";
import { BaseCallbackHandler } from "@langchain/core/callbacks/base";
import { Serialized } from "@langchain/core/load/serializable";
import { LLMResult } from "@langchain/core/outputs";
import { BaseMessage } from "@langchain/core/messages";
import { PIIScrubber } from "./structuredLogger.js";

export function generateTraceId(): string {
  return crypto.randomBytes(16).toString("hex");
}

export function generateSpanId(): string {
  return crypto.randomBytes(8).toString("hex");
}

export interface SpanEvent {
  name: string;
  timeUnixNano: string;
  attributes?: Record<string, unknown>;
}

export class OpenTelemetrySpan {
  name: string;
  traceId: string;
  spanId: string;
  parentSpanId?: string;
  startTimeNs: bigint;
  endTimeNs?: bigint;
  statusCode: "UNSET" | "OK" | "ERROR" = "UNSET";
  statusMessage?: string;
  attributes: Record<string, string | number | boolean>;
  events: SpanEvent[] = [];

  constructor(params: {
    name: string;
    traceId: string;
    spanId: string;
    parentSpanId?: string;
    attributes?: Record<string, string | number | boolean>;
  }) {
    this.name = params.name;
    this.traceId = params.traceId;
    this.spanId = params.spanId;
    this.parentSpanId = params.parentSpanId;
    this.attributes = params.attributes || {};
    this.startTimeNs = process.hrtime.bigint();
  }

  finish(statusCode: "OK" | "ERROR" = "OK", error?: Error | unknown): void {
    this.endTimeNs = process.hrtime.bigint();
    this.statusCode = statusCode;
    if (error) {
      this.statusCode = "ERROR";
      const errObj = error instanceof Error ? error : new Error(String(error));
      this.statusMessage = errObj.message;
      this.events.push({
        name: "exception",
        timeUnixNano: this.endTimeNs.toString(),
        attributes: {
          "exception.type": errObj.name,
          "exception.message": errObj.message,
        },
      });
    }
  }

  get durationMs(): number {
    const end = this.endTimeNs ?? process.hrtime.bigint();
    const diffNs = end - this.startTimeNs;
    return Number(diffNs) / 1_000_000;
  }

  toDict(): Record<string, unknown> {
    return {
      name: this.name,
      traceId: this.traceId,
      spanId: this.spanId,
      parentSpanId: this.parentSpanId,
      durationMs: Math.round(this.durationMs * 100) / 100,
      status: { code: this.statusCode, message: this.statusMessage },
      attributes: this.attributes,
      events: this.events,
    };
  }

  toOtlpFormat(): Record<string, unknown> {
    const isLlm = this.name.includes("chat") || this.name.includes("llm");
    const endNs = this.endTimeNs ?? process.hrtime.bigint();

    return {
      traceId: this.traceId,
      spanId: this.spanId,
      parentSpanId: this.parentSpanId || "",
      name: this.name,
      kind: isLlm ? 3 : 1, // 3: SPAN_KIND_CLIENT, 1: SPAN_KIND_INTERNAL
      startTimeUnixNano: this.startTimeNs.toString(),
      endTimeUnixNano: endNs.toString(),
      attributes: Object.entries(this.attributes).map(([key, val]) => {
        if (typeof val === "number") {
          return Number.isInteger(val)
            ? { key, value: { intValue: String(val) } }
            : { key, value: { doubleValue: val } };
        }
        if (typeof val === "boolean") {
          return { key, value: { boolValue: val } };
        }
        return { key, value: { stringValue: String(val) } };
      }),
      status: {
        code: this.statusCode === "OK" ? 1 : this.statusCode === "ERROR" ? 2 : 0,
        message: this.statusMessage || "",
      },
    };
  }
}

export interface OpenTelemetryGenAIHandlerOptions {
  serviceName?: string;
  traceId?: string;
  threadId?: string;
  userId?: string;
  scrubPii?: boolean;
  spanExporter?: (span: OpenTelemetrySpan) => void;
}

export class OpenTelemetryGenAICallbackHandler extends BaseCallbackHandler {
  name = "opentelemetry_genai_handler";

  serviceName: string;
  traceId: string;
  threadId?: string;
  userId?: string;
  scrubPii: boolean;
  spanExporter?: (span: OpenTelemetrySpan) => void;

  private activeSpans = new Map<string, OpenTelemetrySpan>();
  private _completedSpans: OpenTelemetrySpan[] = [];
  private parentStack: string[] = [];

  constructor(options: OpenTelemetryGenAIHandlerOptions = {}) {
    super();
    this.serviceName = options.serviceName || "telekom-genai-service";
    this.traceId = options.traceId || generateTraceId();
    this.threadId = options.threadId;
    this.userId = options.userId;
    this.scrubPii = options.scrubPii ?? true;
    this.spanExporter = options.spanExporter;
  }

  get completedSpans(): OpenTelemetrySpan[] {
    return this._completedSpans;
  }

  private sanitize(data: unknown): unknown {
    if (!this.scrubPii) return data;
    return PIIScrubber.scrubData(data);
  }

  private currentParentSpanId(): string | undefined {
    return this.parentStack.length > 0 ? this.parentStack[this.parentStack.length - 1] : undefined;
  }

  // ---------------------------------------------------------------------------
  // Chat & LLM Handlers
  // ---------------------------------------------------------------------------

  override async handleChatModelStart(
    llm: Serialized,
    messages: BaseMessage[][],
    runId: string,
    parentRunId?: string,
    extraParams?: Record<string, unknown>
  ): Promise<void> {
    const metadata = (extraParams?.metadata as Record<string, unknown>) || {};
    const invocationParams = (extraParams?.invocation_params as Record<string, unknown>) || {};
    const modelName = String(
      metadata.model_name ||
        metadata.ls_model_name ||
        invocationParams.model ||
        llm.id?.slice(-1)[0] ||
        "chat_model"
    );

    let system = "unknown";
    const lower = modelName.toLowerCase();
    if (lower.includes("gpt")) system = "openai";
    else if (lower.includes("claude")) system = "anthropic";
    else if (lower.includes("gemini")) system = "gemini";

    const span = new OpenTelemetrySpan({
      name: `gen_ai.chat ${modelName}`,
      traceId: this.traceId,
      spanId: generateSpanId(),
      parentSpanId: this.currentParentSpanId(),
      attributes: {
        "gen_ai.system": system,
        "gen_ai.request.model": modelName,
        "gen_ai.operation.name": "chat",
        "service.name": this.serviceName,
      },
    });

    if (this.threadId) span.attributes["session.id"] = this.threadId;
    if (this.userId) span.attributes["user.id"] = this.userId;

    if (messages.length > 0 && messages[0].length > 0) {
      const lastMsg = messages[0][messages[0].length - 1];
      const preview = typeof lastMsg.content === "string" ? lastMsg.content : JSON.stringify(lastMsg.content);
      span.attributes["gen_ai.prompt"] = String(this.sanitize(preview)).slice(0, 500);
    }

    this.activeSpans.set(runId, span);
    this.parentStack.push(span.spanId);
  }

  override async handleLLMEnd(output: LLMResult, runId: string): Promise<void> {
    const span = this.activeSpans.get(runId);
    if (!span) return;
    this.activeSpans.delete(runId);

    const usage = (output.llmOutput?.tokenUsage || output.llmOutput?.estimatedTokenUsage || {}) as Record<string, number>;
    const promptTokens = usage.promptTokens ?? usage.inputTokens ?? 0;
    const completionTokens = usage.completionTokens ?? usage.outputTokens ?? 0;
    const totalTokens = usage.totalTokens ?? (promptTokens + completionTokens);

    span.attributes["gen_ai.usage.prompt_tokens"] = promptTokens;
    span.attributes["gen_ai.usage.completion_tokens"] = completionTokens;
    span.attributes["gen_ai.usage.total_tokens"] = totalTokens;

    if (output.generations.length > 0 && output.generations[0].length > 0) {
      const firstGen = output.generations[0][0];
      span.attributes["gen_ai.completion"] = String(this.sanitize(firstGen.text)).slice(0, 500);
    }

    span.finish("OK");
    if (this.parentStack[this.parentStack.length - 1] === span.spanId) {
      this.parentStack.pop();
    }

    this._completedSpans.push(span);
    if (this.spanExporter) {
      this.spanExporter(span);
    }
  }

  override async handleLLMError(err: Error, runId: string): Promise<void> {
    const span = this.activeSpans.get(runId);
    if (!span) return;
    this.activeSpans.delete(runId);

    span.finish("ERROR", err);
    if (this.parentStack[this.parentStack.length - 1] === span.spanId) {
      this.parentStack.pop();
    }

    this._completedSpans.push(span);
    if (this.spanExporter) {
      this.spanExporter(span);
    }
  }

  // ---------------------------------------------------------------------------
  // Tool Execution Handlers
  // ---------------------------------------------------------------------------

  override async handleToolStart(
    tool: Serialized,
    input: string,
    runId: string
  ): Promise<void> {
    const toolName = tool.id?.slice(-1)[0] || "tool";
    const span = new OpenTelemetrySpan({
      name: `gen_ai.tool ${toolName}`,
      traceId: this.traceId,
      spanId: generateSpanId(),
      parentSpanId: this.currentParentSpanId(),
      attributes: {
        "gen_ai.operation.name": "execute_tool",
        "gen_ai.tool.name": toolName,
        "gen_ai.tool.input": String(this.sanitize(input)).slice(0, 300),
        "service.name": this.serviceName,
      },
    });

    this.activeSpans.set(runId, span);
    this.parentStack.push(span.spanId);
  }

  override async handleToolEnd(output: unknown, runId: string): Promise<void> {
    const span = this.activeSpans.get(runId);
    if (!span) return;
    this.activeSpans.delete(runId);

    span.attributes["gen_ai.tool.output"] = String(this.sanitize(output)).slice(0, 500);
    span.finish("OK");

    if (this.parentStack[this.parentStack.length - 1] === span.spanId) {
      this.parentStack.pop();
    }

    this._completedSpans.push(span);
    if (this.spanExporter) {
      this.spanExporter(span);
    }
  }

  override async handleToolError(err: Error, runId: string): Promise<void> {
    const span = this.activeSpans.get(runId);
    if (!span) return;
    this.activeSpans.delete(runId);

    span.finish("ERROR", err);
    if (this.parentStack[this.parentStack.length - 1] === span.spanId) {
      this.parentStack.pop();
    }

    this._completedSpans.push(span);
    if (this.spanExporter) {
      this.spanExporter(span);
    }
  }

  // ---------------------------------------------------------------------------
  // Chain / Workflow Step Handlers
  // ---------------------------------------------------------------------------

  override async handleChainStart(chain: Serialized, inputs: Record<string, unknown>, runId: string): Promise<void> {
    const chainName = chain.id?.slice(-1)[0] || "workflow";
    const span = new OpenTelemetrySpan({
      name: `workflow.${chainName}`,
      traceId: this.traceId,
      spanId: generateSpanId(),
      parentSpanId: this.currentParentSpanId(),
      attributes: {
        "gen_ai.operation.name": "workflow_step",
        "workflow.name": chainName,
        "service.name": this.serviceName,
      },
    });

    this.activeSpans.set(runId, span);
    this.parentStack.push(span.spanId);
  }

  override async handleChainEnd(outputs: Record<string, unknown>, runId: string): Promise<void> {
    const span = this.activeSpans.get(runId);
    if (!span) return;
    this.activeSpans.delete(runId);

    span.finish("OK");
    if (this.parentStack[this.parentStack.length - 1] === span.spanId) {
      this.parentStack.pop();
    }

    this._completedSpans.push(span);
    if (this.spanExporter) {
      this.spanExporter(span);
    }
  }

  override async handleChainError(err: Error, runId: string): Promise<void> {
    const span = this.activeSpans.get(runId);
    if (!span) return;
    this.activeSpans.delete(runId);

    span.finish("ERROR", err);
    if (this.parentStack[this.parentStack.length - 1] === span.spanId) {
      this.parentStack.pop();
    }

    this._completedSpans.push(span);
    if (this.spanExporter) {
      this.spanExporter(span);
    }
  }

  // ---------------------------------------------------------------------------
  // OTLP Exporter
  // ---------------------------------------------------------------------------

  exportOtlpPayload(): Record<string, unknown> {
    return {
      resourceSpans: [
        {
          resource: {
            attributes: [
              { key: "service.name", value: { stringValue: this.serviceName } },
              { key: "telemetry.sdk.language", value: { stringValue: "typescript" } },
              { key: "telemetry.sdk.name", value: { stringValue: "opentelemetry-genai-bridge" } },
            ],
          },
          scopeSpans: [
            {
              scope: { name: "langchain_suite.otel_bridge", version: "1.0.0" },
              spans: this._completedSpans.map((span) => span.toOtlpFormat()),
            },
          ],
        },
      ],
    };
  }
}

