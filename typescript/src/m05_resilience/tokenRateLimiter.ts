/**
 * Module 5: Enterprise LLM Rate Limiting & Token-Aware Capacity Governor (TypeScript).
 *
 * Implements architectural rate-limiting patterns inspired by WSO2 AI Gateway:
 * 1. Pre-flight Token-Level Quotas: Max prompt tokens, max completion tokens, total token limit (TPM).
 * 2. Cost-Based Rate Limiting: Budget enforcement ($/window) based on real-time token tracking.
 * 3. Real OpenAI Integration: Dispatches verified requests to live OpenAI gpt-4o-mini.
 * 4. Token Usage Reconciliation: Reconciles pre-flight reservations against response.usage.
 * 5. Multi-Tenant Department Isolation: Tiered virtual key quotas with burst absorption.
 * 6. Standard Rate Limit Tracking Headers: Emits X-RateLimit-* and Retry-After.
 *
 * Reference:
 * - WSO2 LLM Rate Limiting Guide: https://wso2.com/api-platform/learn/llm-rate-limiting/
 */

import pc from "picocolors";
import type OpenAI from "openai";
import { getOpenAIClient } from "../m01_paradigms/clientFactory.js";
import { loadWorkspaceEnv } from "../langchain_suite/core/env.js";

loadWorkspaceEnv();

export interface RateLimitHeaders {
  limitTokens: number;
  remainingTokens: number;
  resetTokensSeconds: number;
  retryAfterSeconds?: number;
}

export function formatRateLimitHeaders(headers: RateLimitHeaders): Record<string, string> {
  const result: Record<string, string> = {
    "X-RateLimit-Limit-Tokens": String(headers.limitTokens),
    "X-RateLimit-Remaining-Tokens": String(Math.max(0, headers.remainingTokens)),
    "X-RateLimit-Reset-Tokens": `${Math.ceil(headers.resetTokensSeconds)}s`,
  };
  if (headers.retryAfterSeconds && headers.retryAfterSeconds > 0) {
    result["Retry-After"] = `${Math.ceil(headers.retryAfterSeconds)}`;
  }
  return result;
}

export interface TierPolicy {
  tierName: string;
  maxPromptTokens: number;
  maxCompletionTokens: number;
  totalTokenCapacity: number;
  refillRateTokensPerSec: number;
  maxBudgetUsd: number;
  costPerMillionTokens?: number;
}

export interface AcquireResult {
  allowed: boolean;
  headers: RateLimitHeaders;
  reason: string;
}

export function estimateTokens(text: string): number {
  if (!text || text.trim().length === 0) return 1;
  // Standard rule of thumb: ~4 characters per token for English text
  return Math.max(1, Math.ceil(text.trim().length / 4));
}

export class TokenAwareRateLimiter {
  public policy: TierPolicy;
  public currentTokens: number;
  private lastRefillTimestamp: number;
  public accumulatedCostUsd: number;

  constructor(policy: TierPolicy) {
    this.policy = policy;
    this.currentTokens = policy.totalTokenCapacity;
    this.lastRefillTimestamp = Date.now();
    this.accumulatedCostUsd = 0;
  }

  private refill(): void {
    const now = Date.now();
    const elapsedSec = (now - this.lastRefillTimestamp) / 1000;
    const addedTokens = elapsedSec * this.policy.refillRateTokensPerSec;
    this.currentTokens = Math.min(this.policy.totalTokenCapacity, this.currentTokens + addedTokens);
    this.lastRefillTimestamp = now;
  }

  public acquire(promptTokens: number, estimatedCompletionTokens: number): AcquireResult {
    this.refill();

    // 1. Max Prompt Token enforcement
    if (promptTokens > this.policy.maxPromptTokens) {
      return {
        allowed: false,
        headers: {
          limitTokens: this.policy.totalTokenCapacity,
          remainingTokens: Math.floor(this.currentTokens),
          resetTokensSeconds: 0,
        },
        reason: `PayloadRejected: Prompt tokens (${promptTokens}) exceeded max allowed (${this.policy.maxPromptTokens})`,
      };
    }

    // 2. Max Completion Token enforcement
    if (estimatedCompletionTokens > this.policy.maxCompletionTokens) {
      return {
        allowed: false,
        headers: {
          limitTokens: this.policy.totalTokenCapacity,
          remainingTokens: Math.floor(this.currentTokens),
          resetTokensSeconds: 0,
        },
        reason: `PayloadRejected: Estimated completion tokens (${estimatedCompletionTokens}) exceeded ceiling (${this.policy.maxCompletionTokens})`,
      };
    }

    const totalNeeded = promptTokens + estimatedCompletionTokens;
    const costPerMillion = this.policy.costPerMillionTokens ?? 0.50;
    const callCost = (totalNeeded / 1_000_000) * costPerMillion;

    // 3. Spend budget quota enforcement
    if (this.accumulatedCostUsd + callCost > this.policy.maxBudgetUsd) {
      return {
        allowed: false,
        headers: {
          limitTokens: this.policy.totalTokenCapacity,
          remainingTokens: Math.floor(this.currentTokens),
          resetTokensSeconds: 60,
          retryAfterSeconds: 60,
        },
        reason: `BudgetExceeded: Spend budget exhausted ($${this.accumulatedCostUsd.toFixed(4)} + $${callCost.toFixed(4)} > $${this.policy.maxBudgetUsd.toFixed(2)})`,
      };
    }

    // 4. Token bucket capacity enforcement
    if (totalNeeded > this.currentTokens) {
      const deficit = totalNeeded - this.currentTokens;
      const waitSeconds = this.policy.refillRateTokensPerSec > 0
        ? deficit / this.policy.refillRateTokensPerSec
        : 60.0;
      return {
        allowed: false,
        headers: {
          limitTokens: this.policy.totalTokenCapacity,
          remainingTokens: Math.floor(this.currentTokens),
          resetTokensSeconds: waitSeconds,
          retryAfterSeconds: waitSeconds,
        },
        reason: `HTTP 429 Too Many Requests: Token bucket empty (Deficit: ${Math.ceil(deficit)} tokens. Retry after ${waitSeconds.toFixed(1)}s)`,
      };
    }

    // Deduct tokens and accrue initial estimated cost
    this.currentTokens -= totalNeeded;
    this.accumulatedCostUsd += callCost;
    const resetTime = this.policy.refillRateTokensPerSec > 0
      ? (this.policy.totalTokenCapacity - this.currentTokens) / this.policy.refillRateTokensPerSec
      : 0.0;

    return {
      allowed: true,
      headers: {
        limitTokens: this.policy.totalTokenCapacity,
        remainingTokens: Math.floor(this.currentTokens),
        resetTokensSeconds: resetTime,
      },
      reason: "Accepted",
    };
  }

  public reconcileUsage(
    reservedTotalTokens: number,
    actualPromptTokens: number,
    actualCompletionTokens: number
  ): number {
    const actualTotal = actualPromptTokens + actualCompletionTokens;
    const tokenDelta = reservedTotalTokens - actualTotal; // Positive = refund, Negative = additional debit

    // Adjust bucket token balance
    this.currentTokens = Math.min(
      this.policy.totalTokenCapacity,
      this.currentTokens + tokenDelta
    );

    const costPerMillion = this.policy.costPerMillionTokens ?? 0.50;
    const costDelta = (tokenDelta / 1_000_000) * costPerMillion;
    this.accumulatedCostUsd = Math.max(0, this.accumulatedCostUsd - costDelta);

    return (actualTotal / 1_000_000) * costPerMillion;
  }
}

export interface ExecutionResult {
  scenarioName: string;
  allowed: boolean;
  statusCode: number;
  reason: string;
  headers: RateLimitHeaders;
  promptText: string;
  responseText?: string;
  model: string;
  estimatedPromptTokens: number;
  estimatedCompletionTokens: number;
  actualPromptTokens: number;
  actualCompletionTokens: number;
  totalActualTokens: number;
  callCostUsd: number;
  isLiveCall: boolean;
}

export class OpenAIRateLimitedExecutor {
  private limiter: TokenAwareRateLimiter;
  private model: string;
  private client: OpenAI | null;

  constructor(limiter: TokenAwareRateLimiter, model: string = "gpt-4o-mini", client?: OpenAI | null) {
    this.limiter = limiter;
    this.model = model;
    this.client = client !== undefined ? client : null;
  }

  private getClient(): OpenAI | null {
    if (this.client !== null) return this.client;
    try {
      this.client = getOpenAIClient();
      return this.client;
    } catch {
      return null;
    }
  }

  public async execute(options: {
    scenarioName: string;
    prompt: string;
    systemPrompt?: string;
    maxCompletionTokens?: number;
    simulatedPromptTokens?: number;
    simulatedCompletionTokens?: number;
  }): Promise<ExecutionResult> {
    const systemPrompt = options.systemPrompt ?? "You are a senior Deutsche Telekom network operations AI engineer. Provide concise, highly technical answers.";
    const maxCompletionTokens = options.maxCompletionTokens ?? 150;
    const fullText = `${systemPrompt}\n${options.prompt}`;

    const estimatedPromptTokens = options.simulatedPromptTokens !== undefined
      ? options.simulatedPromptTokens
      : estimateTokens(fullText);

    const estimatedCompletionTokens = options.simulatedCompletionTokens !== undefined
      ? options.simulatedCompletionTokens
      : maxCompletionTokens;

    const totalReserved = estimatedPromptTokens + estimatedCompletionTokens;

    // 1. Pre-flight Rate Limiting Check
    const decision = this.limiter.acquire(estimatedPromptTokens, estimatedCompletionTokens);

    if (!decision.allowed) {
      let statusCode = 429;
      if (decision.reason.includes("PayloadRejected")) {
        statusCode = 400;
      } else if (decision.reason.includes("BudgetExceeded")) {
        statusCode = 402;
      }
      return {
        scenarioName: options.scenarioName,
        allowed: false,
        statusCode,
        reason: decision.reason,
        headers: decision.headers,
        promptText: options.prompt,
        model: this.model,
        estimatedPromptTokens,
        estimatedCompletionTokens,
        actualPromptTokens: 0,
        actualCompletionTokens: 0,
        totalActualTokens: 0,
        callCostUsd: 0.0,
        isLiveCall: false,
      };
    }

    // 2. Dispatch Live OpenAI Call
    const client = this.getClient();
    let responseText = "";
    let actualPromptTokens = estimatedPromptTokens;
    let actualCompletionTokens = estimatedCompletionTokens;
    let isLiveCall = false;

    if (client) {
      try {
        const completion = await client.chat.completions.create({
          model: this.model,
          messages: [
            { role: "system", content: systemPrompt },
            { role: "user", content: options.prompt },
          ],
          max_tokens: maxCompletionTokens,
          temperature: 0.2,
        });

        responseText = completion.choices[0]?.message?.content ?? "";
        isLiveCall = true;

        if (completion.usage) {
          actualPromptTokens = completion.usage.prompt_tokens;
          actualCompletionTokens = completion.usage.completion_tokens;
        }
      } catch (err: any) {
        responseText = `[OpenAI Error]: ${err.message}`;
      }
    } else {
      responseText = "[Simulated Response]: OpenAI client not initialized.";
    }

    // 3. Post-call Usage Reconciliation
    const actualCost = this.limiter.reconcileUsage(
      totalReserved,
      actualPromptTokens,
      actualCompletionTokens
    );

    return {
      scenarioName: options.scenarioName,
      allowed: true,
      statusCode: 200,
      reason: "Accepted",
      headers: decision.headers,
      promptText: options.prompt,
      responseText,
      model: this.model,
      estimatedPromptTokens,
      estimatedCompletionTokens,
      actualPromptTokens,
      actualCompletionTokens,
      totalActualTokens: actualPromptTokens + actualCompletionTokens,
      callCostUsd: actualCost,
      isLiveCall,
    };
  }
}

export async function demonstrateOpenAIRateLimiting(): Promise<void> {
  console.log(pc.bold(pc.cyan("\n========================================================================")));
  console.log(pc.bold(pc.cyan("  WSO2 Pattern: Enterprise LLM Rate Limiter & Governor (Live OpenAI)   ")));
  console.log(pc.bold(pc.cyan("========================================================================\n")));

  // Enterprise Tier: Telecom NOC Production Tier
  const policy: TierPolicy = {
    tierName: "Telekom-NOC-Tier",
    maxPromptTokens: 4000,
    maxCompletionTokens: 1000,
    totalTokenCapacity: 2500,
    refillRateTokensPerSec: 200, // 200 tokens/sec = 12,000 TPM
    maxBudgetUsd: 0.05,
    costPerMillionTokens: 0.50, // $0.50 per 1M tokens ($0.0005/1K)
  };

  const limiter = new TokenAwareRateLimiter(policy);
  const executor = new OpenAIRateLimitedExecutor(limiter, "gpt-4o-mini");

  const scenarios = [
    {
      name: "1. SIM 5G SA Provisioning",
      prompt: "Subscriber IMSI 26201984210001 status is ACTIVE. Verify if 5G SA network slicing (SST=1, SD=0x000001) is supported and specify the default 5QI.",
      maxCompletionTokens: 80,
    },
    {
      name: "2. BGP Peering Root Cause",
      prompt: "Incident INC-7702: BGP session flapping between AS3320 (Telekom) and AS15169 (Google) on Frankfurt IX interface TenGigE0/1/0. Output 3 immediate mitigation steps.",
      maxCompletionTokens: 120,
    },
    {
      name: "3. Runaway Syslog Dump (Ceiling Breach)",
      prompt: "Correlate the following raw firewall syslog dump containing 85,000 lines of drop events...",
      maxCompletionTokens: 100,
      simulatedPromptTokens: 4600, // Exceeds maxPromptTokens (4000)
    },
    {
      name: "4. Unbounded Generation (Completion Breach)",
      prompt: "Generate an exhaustive inventory of all 45,000 active cell sites across Germany with micro-cell antenna configurations.",
      maxCompletionTokens: 1500, // Exceeds maxCompletionTokens (1000)
    },
    {
      name: "5. Rapid Burst Surge (Capacity Drain)",
      prompt: "Perform emergency global trace of all active SIP trunks across European data centers and evaluate SIP 503 response rates.",
      maxCompletionTokens: 200,
      simulatedPromptTokens: 950, // 950 + 200 = 1150 tokens. Will drain bucket.
    },
    {
      name: "6. Post-Cooldown Recovery",
      prompt: "Health check: Are all 5G UPF (User Plane Function) nodes in Berlin cluster DE-BER-01 reporting nominal latency?",
      maxCompletionTokens: 60,
      waitForCooldownSec: 2.5,
    },
  ];

  const results: ExecutionResult[] = [];

  for (const sc of scenarios) {
    if (sc.waitForCooldownSec) {
      console.log(pc.yellow(`Sleeping ${sc.waitForCooldownSec}s to allow token bucket refill...`));
      await new Promise((r) => setTimeout(r, sc.waitForCooldownSec * 1000));
    }

    const res = await executor.execute({
      scenarioName: sc.name,
      prompt: sc.prompt,
      maxCompletionTokens: sc.maxCompletionTokens,
      simulatedPromptTokens: sc.simulatedPromptTokens,
      simulatedCompletionTokens: sc.simulatedPromptTokens ? undefined : (sc.maxCompletionTokens > policy.maxCompletionTokens ? sc.maxCompletionTokens : undefined),
    });
    results.push(res);
  }

  // Display summary table
  console.log("\n" + pc.bold("Enterprise LLM Gateway Rate Limiting with Live OpenAI Execution"));
  console.log("-".repeat(100));
  console.log(
    "Scenario".padEnd(28) +
    "Status / Verdict".padEnd(24) +
    "Tokens (Res / Act)".padEnd(22) +
    "Bucket Rem.".padEnd(14) +
    "Retry-After"
  );
  console.log("-".repeat(100));

  for (const r of results) {
    const formattedHeaders = formatRateLimitHeaders(r.headers);
    const retryStr = formattedHeaders["Retry-After"] ?? "-";

    let statusText: string;
    if (r.allowed) {
      statusText = pc.green(`200 OK (${r.isLiveCall ? "Live Call" : "Simulated"})`);
    } else if (r.statusCode === 400) {
      statusText = pc.red("400 Rejected");
    } else if (r.statusCode === 429) {
      statusText = pc.yellow("429 Throttled");
    } else {
      statusText = pc.magenta(`${r.statusCode} Capped`);
    }

    const tokensStr = r.allowed
      ? `${r.estimatedPromptTokens + r.estimatedCompletionTokens} / ${r.totalActualTokens}`
      : `${r.estimatedPromptTokens + r.estimatedCompletionTokens} / 0`;

    console.log(
      r.scenarioName.padEnd(28) +
      statusText.padEnd(33) +
      tokensStr.padEnd(22) +
      String(r.headers.remainingTokens).padEnd(14) +
      retryStr
    );
  }
  console.log("-".repeat(100));
  console.log(pc.bold(pc.green(`Cumulative Spend: $${limiter.accumulatedCostUsd.toFixed(6)} / $${policy.maxBudgetUsd.toFixed(2)}\n`)));

  // Display Live Responses
  console.log(pc.bold(pc.cyan("=== Live OpenAI Responses from Accepted Scenarios ===\n")));
  for (const r of results) {
    if (r.allowed && r.responseText) {
      console.log(pc.bold(pc.blue(`--- [${r.scenarioName}] ---`)));
      console.log(pc.dim(`Prompt: ${r.promptText}`));
      console.log(pc.green(`OpenAI (${r.model}) Response:\n${r.responseText.trim()}`));
      console.log(pc.dim(`Tokens: ${r.actualPromptTokens} in + ${r.actualCompletionTokens} out = ${r.totalActualTokens} total | Cost: $${r.callCostUsd.toFixed(6)}\n`));
    }
  }
}

// Preserve backward-compatible alias
export const demonstrateEnterpriseRateLimiting = demonstrateOpenAIRateLimiting;

if (process.argv[1]?.includes("tokenRateLimiter")) {
  demonstrateOpenAIRateLimiting().catch(console.error);
}
