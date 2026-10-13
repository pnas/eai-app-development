/**
 * Module 5 (LangChain TypeScript): Token-Aware Rate Limiting Runnable & Enterprise Governor.
 *
 * Demonstrates integrating WSO2-style LLM rate-limiting policies into LangChain
 * runnables, chains, and multi-provider fallbacks:
 * 1. Token Bucket evaluation before model invocation (pre-call quota check).
 * 2. Inspection of prompt and completion token constraints.
 * 3. Fallback cascade trigger on RateLimitExceededError (HTTP 429).
 * 4. Standard response metadata injection with token budget status.
 *
 * Reference:
 * - WSO2 LLM Rate Limiting Guide: https://wso2.com/api-platform/learn/llm-rate-limiting/
 */

import { AIMessage, BaseMessage, HumanMessage } from "@langchain/core/messages";
import { BaseChatModel } from "@langchain/core/language_models/chat_models";
import { ChatResult } from "@langchain/core/outputs";
import pc from "picocolors";

export class RateLimitExceededError extends Error {
  retryAfter: number;
  status: number;

  constructor(message: string, retryAfter = 2.0) {
    super(message);
    this.name = "RateLimitExceededError";
    this.retryAfter = retryAfter;
    this.status = 429;
  }
}

export class LangChainTokenRateLimiter {
  maxPromptTokens: number;
  maxCompletionTokens: number;
  capacityTokens: number;
  refillRatePerSec: number;
  currentTokens: number;
  lastRefill: number;

  constructor(
    maxPromptTokens = 2000,
    maxCompletionTokens = 1000,
    capacityTokens = 5000,
    refillRatePerSec = 1000
  ) {
    this.maxPromptTokens = maxPromptTokens;
    this.maxCompletionTokens = maxCompletionTokens;
    this.capacityTokens = capacityTokens;
    this.refillRatePerSec = refillRatePerSec;
    this.currentTokens = capacityTokens;
    this.lastRefill = Date.now();
  }

  private refill(): void {
    const now = Date.now();
    const elapsedSec = (now - this.lastRefill) / 1000;
    this.currentTokens = Math.min(this.capacityTokens, this.currentTokens + elapsedSec * this.refillRatePerSec);
    this.lastRefill = now;
  }

  checkAndConsume(
    promptTokens: number,
    completionTokens = 500
  ): { consumed: number; remaining: number; limit: number } {
    this.refill();

    // Enforce Prompt Ceiling (WSO2 LLM Rule)
    if (promptTokens > this.maxPromptTokens) {
      throw new Error(
        `PayloadRejected: Prompt tokens (${promptTokens}) exceed maximum limit (${this.maxPromptTokens})`
      );
    }

    const totalTokens = promptTokens + completionTokens;
    if (totalTokens > this.currentTokens) {
      const deficit = totalTokens - this.currentTokens;
      const retryAfter = deficit / this.refillRatePerSec;
      throw new RateLimitExceededError(
        `HTTP 429 Too Many Requests: TPM bucket exhausted. Deficit: ${Math.round(deficit)} tokens.`,
        retryAfter
      );
    }

    this.currentTokens -= totalTokens;
    return {
      consumed: totalTokens,
      remaining: Math.round(this.currentTokens),
      limit: Math.round(this.capacityTokens),
    };
  }
}

export class RateLimitedMockModel extends BaseChatModel {
  modelName: string;
  governor: LangChainTokenRateLimiter;

  constructor(modelName: string, governor: LangChainTokenRateLimiter) {
    super({});
    this.modelName = modelName;
    this.governor = governor;
  }

  _llmType(): string {
    return "rate_limited_mock";
  }

  async _generate(messages: BaseMessage[]): Promise<ChatResult> {
    const totalPromptText = messages.map((m) => (typeof m.content === "string" ? m.content : "")).join("");
    const promptTokens = Math.max(1, Math.floor(totalPromptText.length / 4));

    // Enforce pre-call Token Bucket inspection
    const stats = this.governor.checkAndConsume(promptTokens);

    const content = `[${this.modelName}] Diagnostic query executed within token budget.`;
    return {
      generations: [
        {
          text: content,
          message: new AIMessage({
            content,
            response_metadata: {
              model: this.modelName,
              tokens_remaining: stats.remaining,
              rate_limit_policy: "WSO2-Token-Bucket",
            },
          }),
        },
      ],
    };
  }
}

export class BackupMockModel extends BaseChatModel {
  modelName: string;

  constructor(modelName = "backup-overflow-model") {
    super({});
    this.modelName = modelName;
  }

  _llmType(): string {
    return "backup_mock";
  }

  async _generate(_messages: BaseMessage[]): Promise<ChatResult> {
    const content = `[${this.modelName}] Failover successful: Handled request via secondary tier pool.`;
    return {
      generations: [
        {
          text: content,
          message: new AIMessage({
            content,
            response_metadata: {
              model: this.modelName,
              failover_reason: "429_RATE_LIMIT",
            },
          }),
        },
      ],
    };
  }
}

export async function demonstrateLangChainRateLimiting(): Promise<void> {
  console.log(
    pc.cyan(
      "\n=== LangChain Integration: WSO2 Token Rate Limiter & Fallback Cascade (TypeScript) ===\n"
    )
  );

  // Governor with 1,500 token capacity and 50 tokens/sec refill to demonstrate exhaustion
  const governor = new LangChainTokenRateLimiter(2000, 800, 1500, 50);

  const primary = new RateLimitedMockModel("claude-haiku-5-5 (Primary Rate-Limited)", governor);
  const backup = new BackupMockModel("gpt-4.1-mini (Secondary Surge Fallback)");

  // Declarative LangChain fallback on 429 RateLimitExceededError
  const resilientChain = primary.withFallbacks({
    fallbacks: [backup],
  });

  const requests = [
    "Check BGP peering session status on Router R-01.",
    "Inspect telemetry statistics for optical link Frankfurt-Paris.",
    "Analyze memory buffer saturation on edge leaf switches.", // Bucket exhausted -> 429 -> Failover to backup
  ];

  for (let i = 0; i < requests.length; i++) {
    const req = requests[i];
    console.log(pc.yellow(`Request #${i + 1}: `) + `"${req.slice(0, 50)}..."`);
    try {
      const res = await resilientChain.invoke([new HumanMessage(req)]);
      console.log(pc.green(`  Result: `) + `${res.content}`);
      const meta = res.response_metadata || {};
      console.log(pc.magenta(`  Metadata: `) + `${JSON.stringify(meta)}\n`);
    } catch (err: any) {
      console.log(pc.red(`  Failed with error: ${err.message}\n`));
    }
  }
}

if (process.argv[1]?.includes("rateLimitedChain")) {
  demonstrateLangChainRateLimiting().catch(console.error);
}
