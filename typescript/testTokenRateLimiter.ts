import test from "node:test";
import assert from "node:assert/strict";
import { HumanMessage } from "@langchain/core/messages";
import {
  TokenAwareRateLimiter,
  TierPolicy,
  formatRateLimitHeaders,
} from "./src/m05_resilience/tokenRateLimiter.js";
import {
  LangChainTokenRateLimiter,
  RateLimitedMockModel,
  BackupMockModel,
  RateLimitExceededError,
} from "./src/langchain_suite/m05_resilience/rateLimitedChain.js";

test("TokenAwareRateLimiter: Rejects prompt exceeding tier max prompt ceiling", () => {
  const policy: TierPolicy = {
    tierName: "test-tier",
    maxPromptTokens: 100,
    maxCompletionTokens: 50,
    totalTokenCapacity: 1000,
    refillRateTokensPerSec: 100,
    maxBudgetUsd: 10.0,
    costPerMillionTokens: 1.0,
  };
  const limiter = new TokenAwareRateLimiter(policy);
  const result = limiter.acquire(150, 20);

  assert.equal(result.allowed, false);
  assert.match(result.reason, /Prompt tokens.*exceeded max allowed/);
});

test("TokenAwareRateLimiter: Rejects completion request exceeding completion ceiling", () => {
  const policy: TierPolicy = {
    tierName: "test-tier",
    maxPromptTokens: 500,
    maxCompletionTokens: 100,
    totalTokenCapacity: 1000,
    refillRateTokensPerSec: 100,
    maxBudgetUsd: 10.0,
    costPerMillionTokens: 1.0,
  };
  const limiter = new TokenAwareRateLimiter(policy);
  const result = limiter.acquire(50, 150);

  assert.equal(result.allowed, false);
  assert.match(result.reason, /Estimated completion tokens.*exceeded ceiling/);
});

test("TokenAwareRateLimiter: Enforces token bucket capacity and provides retry-after header", () => {
  const policy: TierPolicy = {
    tierName: "strict-tpm",
    maxPromptTokens: 1000,
    maxCompletionTokens: 500,
    totalTokenCapacity: 500,
    refillRateTokensPerSec: 50,
    maxBudgetUsd: 50.0,
    costPerMillionTokens: 2.0,
  };
  const limiter = new TokenAwareRateLimiter(policy);

  // Consume full bucket
  const decision1 = limiter.acquire(200, 250);
  assert.equal(decision1.allowed, true);

  // Subsequent call breaches bucket
  const decision2 = limiter.acquire(100, 100);
  assert.equal(decision2.allowed, false);
  assert.match(decision2.reason, /HTTP 429 Too Many Requests/);
  assert.ok(decision2.headers.retryAfterSeconds && decision2.headers.retryAfterSeconds > 0);

  const formatted = formatRateLimitHeaders(decision2.headers);
  assert.ok(formatted["Retry-After"]);
  assert.ok(formatted["X-RateLimit-Reset-Tokens"]);
});

test("TokenAwareRateLimiter: Enforces cost budget ceiling across aggregated consumption", () => {
  const policy: TierPolicy = {
    tierName: "budget-capped",
    maxPromptTokens: 10000,
    maxCompletionTokens: 5000,
    totalTokenCapacity: 100000,
    refillRateTokensPerSec: 10000,
    maxBudgetUsd: 0.005, // Cap at half a cent
    costPerMillionTokens: 10.0,  // $10 per 1M -> 0.005 budget reached at 500 tokens
  };
  const limiter = new TokenAwareRateLimiter(policy);

  // First request: 300 tokens -> $0.003
  const res1 = limiter.acquire(100, 200);
  assert.equal(res1.allowed, true);

  // Second request: 300 tokens -> would exceed $0.005 budget
  const res2 = limiter.acquire(100, 200);
  assert.equal(res2.allowed, false);
  assert.match(res2.reason, /BudgetExceeded/);
});

test("LangChain Integration: Fallback cascade triggers on RateLimitExceededError (429)", async () => {
  const governor = new LangChainTokenRateLimiter(500, 200, 100, 10);
  const primary = new RateLimitedMockModel("primary-llm", governor);
  const backup = new BackupMockModel("backup-llm");

  const resilientChain = primary.withFallbacks({
    fallbacks: [backup],
  });

  // Direct governor call with tokens > capacity triggers RateLimitExceededError
  assert.throws(
    () => governor.checkAndConsume(150, 100),
    (err: any) => {
      assert.ok(err instanceof RateLimitExceededError);
      assert.equal(err.status, 429);
      return true;
    }
  );

  // Invoking chain triggers automatic failover to backup model
  const response = await resilientChain.invoke([
    new HumanMessage("This long query will drain and breach the 100-token capacity governor!"),
  ]);

  assert.ok(String(response.content).includes("backup-llm"));
  assert.equal(response.response_metadata?.failover_reason, "429_RATE_LIMIT");
});

test("TokenAwareRateLimiter: Reconciles usage and adjusts token capacity and financial spend", () => {
  const policy: TierPolicy = {
    tierName: "reconcile-tier",
    maxPromptTokens: 2000,
    maxCompletionTokens: 1000,
    totalTokenCapacity: 5000,
    refillRateTokensPerSec: 0, // Freeze refill for deterministic token arithmetic
    maxBudgetUsd: 10.0,
    costPerMillionTokens: 1.0,
  };
  const limiter = new TokenAwareRateLimiter(policy);

  // Reserve 400 prompt + 200 completion = 600 tokens
  const decision = limiter.acquire(400, 200);
  assert.equal(decision.allowed, true);
  assert.equal(limiter.currentTokens, 4400);

  // Model actually used 300 prompt + 50 completion = 350 tokens (refund 250 tokens)
  const actualCost = limiter.reconcileUsage(600, 300, 50);
  assert.equal(limiter.currentTokens, 4650);
  assert.ok(Math.abs(actualCost - 0.00035) < 1e-8);
  assert.ok(Math.abs(limiter.accumulatedCostUsd - 0.00035) < 1e-8);
});

test("OpenAIRateLimitedExecutor: Pre-flight ceiling rejection returns 400 without API dispatch", async () => {
  const { OpenAIRateLimitedExecutor } = await import("./src/m05_resilience/tokenRateLimiter.js");
  const policy: TierPolicy = {
    tierName: "ceiling-test-tier",
    maxPromptTokens: 50,
    maxCompletionTokens: 50,
    totalTokenCapacity: 1000,
    refillRateTokensPerSec: 100,
    maxBudgetUsd: 1.0,
  };
  const limiter = new TokenAwareRateLimiter(policy);
  const executor = new OpenAIRateLimitedExecutor(limiter, "gpt-4o-mini", null);

  const longPrompt = "Tell me everything about telecommunications and 5G network slicing ".repeat(10);
  const result = await executor.execute({
    scenarioName: "Ceiling Breach Test",
    prompt: longPrompt,
    maxCompletionTokens: 20,
  });

  assert.equal(result.allowed, false);
  assert.equal(result.statusCode, 400);
  assert.match(result.reason, /PayloadRejected/);
  assert.equal(result.responseText, undefined);
  assert.equal(result.isLiveCall, false);
});

