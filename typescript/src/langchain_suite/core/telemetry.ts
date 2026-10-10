import { BaseCallbackHandler } from "@langchain/core/callbacks/base";
import { Serialized } from "@langchain/core/load/serializable";
import { LLMResult } from "@langchain/core/outputs";
import pc from "picocolors";

export interface AuditRecord {
  runId: string;
  stepType: "llm" | "tool" | "chain";
  durationSeconds: number;
  totalTokens?: number;
}

export class AuditTelemetryHandler extends BaseCallbackHandler {
  name = "AuditTelemetryHandler";
  private startTimes = new Map<string, number>();
  public records: AuditRecord[] = [];

  constructor(private verbose: boolean = true) {
    super();
  }

  handleChatModelStart(llm: Serialized, messages: unknown[][], runId: string): void {
    this.startTimes.set(runId, performance.now());
    if (this.verbose) {
      console.log(
        pc.cyan(`🔍 [START LLM] runId=${runId.slice(0, 8)} turns=${messages[0]?.length ?? 0}`)
      );
    }
  }

  handleLLMEnd(output: LLMResult, runId: string): void {
    const start = this.startTimes.get(runId) ?? performance.now();
    this.startTimes.delete(runId);
    const duration = (performance.now() - start) / 1000;

    const tokenUsage = output.llmOutput?.tokenUsage;
    const totalTokens = tokenUsage?.totalTokens ?? 0;

    this.records.push({
      runId,
      stepType: "llm",
      durationSeconds: duration,
      totalTokens,
    });

    if (this.verbose) {
      console.log(
        pc.green(
          `✅ [END LLM] runId=${runId.slice(0, 8)} duration=${duration.toFixed(3)}s tokens=${totalTokens || "N/A"}`
        )
      );
    }
  }

  handleToolStart(tool: Serialized, input: string, runId: string): void {
    this.startTimes.set(runId, performance.now());
    if (this.verbose) {
      const toolName = tool.id?.at(-1) ?? "tool";
      console.log(pc.magenta(`🛠️  [TOOL INVOKE] runId=${runId.slice(0, 8)} tool=${toolName} input=${input.slice(0, 60)}`));
    }
  }

  handleToolEnd(output: string, runId: string): void {
    const start = this.startTimes.get(runId) ?? performance.now();
    this.startTimes.delete(runId);
    const duration = (performance.now() - start) / 1000;

    this.records.push({
      runId,
      stepType: "tool",
      durationSeconds: duration,
    });

    if (this.verbose) {
      console.log(pc.magenta(`📥 [TOOL RESULT] runId=${runId.slice(0, 8)} duration=${duration.toFixed(3)}s output=${output.slice(0, 60)}`));
    }
  }

  handleChainError(err: Error, runId: string): void {
    if (this.verbose) {
      console.log(pc.red(`❌ [CHAIN ERROR] runId=${runId.slice(0, 8)}: ${err.message}`));
    }
  }

  getSummary() {
    const totalDuration = this.records.reduce((acc, r) => acc + r.durationSeconds, 0);
    const totalTokens = this.records.reduce((acc, r) => acc + (r.totalTokens ?? 0), 0);
    return {
      totalSteps: this.records.length,
      totalDurationSeconds: Number(totalDuration.toFixed(3)),
      totalTokens,
    };
  }
}

