/**
 * Module 5: Provider HTTP Error Code Taxonomy & Normalized Exceptions (TypeScript).
 *
 * Normalizes vendor-specific errors (OpenAI, Anthropic, Google Gemini) into
 * actionable enterprise domain exceptions.
 */

import pc from "picocolors";
import type OpenAI from "openai";
import { getOpenAIClient } from "../m01_paradigms/clientFactory.js";
import { loadWorkspaceEnv } from "../langchain_suite/core/env.js";

loadWorkspaceEnv();

export class GenAIError extends Error {
  public retryable: boolean;
  public statusCode: number;

  constructor(message: string, retryable = false, statusCode = 500) {
    super(message);
    this.name = "GenAIError";
    this.retryable = retryable;
    this.statusCode = statusCode;
  }
}

export class RateLimitExceededError extends GenAIError {
  public retryAfterSeconds: number;
  public errorCode: string;

  constructor(message: string, retryAfterSeconds = 5.0, errorCode = "rate_limit_exceeded") {
    super(message, true, 429);
    this.name = "RateLimitExceededError";
    this.retryAfterSeconds = retryAfterSeconds;
    this.errorCode = errorCode;
  }
}

export class ContextLengthExceededError extends GenAIError {
  constructor(message: string) {
    super(message, false, 400);
    this.name = "ContextLengthExceededError";
  }
}

export class ProviderOverloadedError extends GenAIError {
  constructor(message: string, statusCode = 503) {
    super(message, true, statusCode);
    this.name = "ProviderOverloadedError";
  }
}

export class AuthenticationError extends GenAIError {
  constructor(message: string) {
    super(message, false, 401);
    this.name = "AuthenticationError";
  }
}

export class TransientServerError extends GenAIError {
  constructor(message: string) {
    super(message, true, 500);
    this.name = "TransientServerError";
  }
}

export function normalizeProviderError(error: any): GenAIError {
  const msg = error?.message || String(error);
  const status = error?.status || error?.statusCode || 500;

  if (status === 401 || status === 403 || msg.includes("API key") || msg.includes("unauthorized")) {
    return new AuthenticationError(msg);
  }
  if (status === 429 || msg.includes("rate_limit") || msg.includes("RESOURCE_EXHAUSTED")) {
    return new RateLimitExceededError(msg, 5.0);
  }
  if (status === 529 || status === 503 || msg.includes("overloaded") || msg.includes("capacity")) {
    return new ProviderOverloadedError(msg, status);
  }
  if (
    status === 400 &&
    (msg.includes("context_length") ||
      msg.includes("token limit") ||
      msg.includes("maximum context") ||
      msg.includes("max_tokens is too large"))
  ) {
    return new ContextLengthExceededError(msg);
  }
  if (status >= 500) {
    return new TransientServerError(msg);
  }
  return new GenAIError(msg, false, status);
}

async function demonstrateLiveTaxonomy() {
  console.log(pc.bold("\n=== Enterprise GenAI Error Taxonomy: Live OpenAI & Error Injection ==="));
  console.log(pc.dim("Testing live OpenAI API requests. If >= 2 attempts succeed without error, an error is injected to showcase normalization...\n"));

  let client: OpenAI | null = null;
  try {
    client = getOpenAIClient();
  } catch (err: any) {
    console.log(pc.yellow(`⚠️  OpenAI client initialization skipped: ${err.message}`));
  }

  if (!client) {
    console.log(pc.yellow("No live OpenAI API key available. Skipping live dispatch."));
    return;
  }

  // Scenarios targeting different API behavior
  const liveScenarios = [
    {
      name: "1. Nominal Request (gpt-4o-mini)",
      prompt: "Summarize 5G SA network slicing in 10 words.",
      params: { max_tokens: 25 },
    },
    {
      name: "2. Nominal Request #2 (Telecom BGP Diagnostic)",
      prompt: "State 1 mitigation for BGP route flapping in 10 words.",
      params: { max_tokens: 25 },
    },
    {
      name: "3. Parameter / Context Window Ceiling (max_tokens: 2,000,000)",
      prompt: "Diagnostic dump",
      params: { max_tokens: 2000000 },
    },
    {
      name: "4. Rate Limit / Transient Overload (Demonstration Injection)",
      prompt: "Ping UPF node",
      params: { max_tokens: 10 },
      forceInjectAfter2Successes: true,
    },
  ];

  console.log("Scenario / Provider Call".padEnd(46) + "Outcome / Normalized Class".padEnd(30) + "Retryable");
  console.log("-".repeat(90));

  let consecutiveSuccesses = 0;

  for (const scenario of liveScenarios) {
    try {
      // If after 2 attempts we don't get any error from OpenAI, inject an error to showcase normalization
      if (scenario.forceInjectAfter2Successes && consecutiveSuccesses >= 2) {
        console.log(pc.magenta(`   [Injection] ${consecutiveSuccesses} consecutive successful calls observed from OpenAI.`));
        console.log(pc.magenta("   [Injection] Injecting simulated OpenAI 429 RateLimitError (TPM quota exceeded) to demonstrate resilience..."));
        const injectedErr: any = new Error("429 Too Many Requests: TPM quota exceeded for model gpt-4o-mini (Injected for demonstration)");
        injectedErr.status = 429;
        throw injectedErr;
      }

      const res = await client.chat.completions.create({
        model: "gpt-4o-mini",
        messages: [{ role: "user", content: scenario.prompt }],
        ...scenario.params,
      });

      consecutiveSuccesses++;
      const text = res.choices[0]?.message?.content?.trim()?.replace(/\n/g, " ")?.slice(0, 28) || "200 OK";
      console.log(
        scenario.name.slice(0, 44).padEnd(46) +
        pc.green(`200 OK: "${text}..."`).padEnd(39) +
        pc.dim("N/A")
      );
    } catch (err: any) {
      const normalized = normalizeProviderError(err);
      const retryStr = normalized.retryable ? pc.green("YES (Backoff)") : pc.red("NO (Fail-Fast)");
      console.log(
        scenario.name.slice(0, 44).padEnd(46) +
        pc.bold(normalized.constructor.name).padEnd(30) +
        retryStr
      );
      console.log(pc.dim(`   ↳ Raw Error: [${err.status || 500}] ${err.message?.slice(0, 75)}...`));
    }
  }
  console.log("-".repeat(90) + "\n");
}

async function main() {
  console.log(pc.bold("\n=== Enterprise GenAI Error Taxonomy Normalization ===\n"));

  const rawErrors = [
    { provider: "Anthropic", raw: { status: 529, message: "Overloaded: Claude infrastructure capacity reached" } },
    { provider: "OpenAI", raw: { status: 429, message: "Rate limit reached for requests per minute (RPM)" } },
    { provider: "Google Gemini", raw: { status: 429, message: "RESOURCE_EXHAUSTED: quota exceeded for quota metric" } },
    { provider: "OpenAI", raw: { status: 400, message: "Invalid request: context_length_exceeded (prompt has 135,000 tokens)" } },
    { provider: "Anthropic", raw: { status: 401, message: "x-api-key header invalid or expired" } },
  ];

  console.log("Raw Provider Error".padEnd(45) + "Normalized Class".padEnd(30) + "Retryable");
  console.log("-".repeat(85));

  for (const item of rawErrors) {
    const normalized = normalizeProviderError(item.raw);
    const retryStr = normalized.retryable ? pc.green("YES (Backoff)") : pc.red("NO (Fail-Fast)");
    console.log(
      `[${item.provider}] ${item.raw.message}`.slice(0, 42).padEnd(45) +
      normalized.constructor.name.padEnd(30) +
      retryStr
    );
  }
  console.log("-".repeat(85));

  // Run live calls with OpenAI and demonstration error injection
  await demonstrateLiveTaxonomy();
}

if (process.argv[1]?.includes("errorTaxonomy")) {
  main().catch(console.error);
}
