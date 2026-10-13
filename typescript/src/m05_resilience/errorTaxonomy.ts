/**
 * Module 5: Provider HTTP Error Code Taxonomy & Normalized Exceptions (TypeScript).
 *
 * Normalizes vendor-specific errors (OpenAI, Anthropic, Google Gemini) into
 * actionable enterprise domain exceptions.
 */

import pc from "picocolors";

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
  if (status === 400 && (msg.includes("context_length") || msg.includes("token limit") || msg.includes("maximum context"))) {
    return new ContextLengthExceededError(msg);
  }
  if (status >= 500) {
    return new TransientServerError(msg);
  }
  return new GenAIError(msg, false, status);
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
  console.log("-".repeat(85) + "\n");
}

if (process.argv[1]?.includes("errorTaxonomy")) {
  main().catch(console.error);
}
