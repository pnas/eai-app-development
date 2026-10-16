import pc from "picocolors";
import type OpenAI from "openai";
import { getOpenAIClient } from "../m01_paradigms/clientFactory.js";
import { loadWorkspaceEnv } from "../langchain_suite/core/env.js";

loadWorkspaceEnv();

export interface RetryOptions {
  maxRetries?: number;
  baseBackoffMs?: number;
  maxBackoffMs?: number;
  retryableErrors?: string[];
}

export async function retryWithFullJitter<T>(
  fn: (attemptNumber: number) => Promise<T>,
  options: RetryOptions = {}
): Promise<T> {
  const maxRetries = options.maxRetries ?? 3;
  const baseBackoffMs = options.baseBackoffMs ?? 500;
  const maxBackoffMs = options.maxBackoffMs ?? 4000;

  let attempt = 0;

  while (true) {
    try {
      return await fn(attempt);
    } catch (err: any) {
      attempt++;
      if (attempt > maxRetries) {
        console.log(pc.red(`\n✘ Exceeded max retries (${maxRetries}). Rethrowing error.`));
        throw err;
      }

      // Full Jitter formula: sleep = rand(0, min(maxBackoffMs, baseBackoffMs * 2^attempt))
      const ceiling = Math.min(maxBackoffMs, baseBackoffMs * Math.pow(2, attempt));
      const jitteredSleepMs = Math.floor(Math.random() * ceiling);

      console.log(
        pc.yellow(
          `   ⚠️  Attempt ${attempt} encountered error [${err.status || err.name || "Error"}]: ${err.message?.slice(0, 75)}... ` +
          `\n   ⏳ Backing off with Full Jitter: ${jitteredSleepMs}ms (exponential ceiling: ${ceiling}ms)...`
        )
      );

      await new Promise((resolve) => setTimeout(resolve, jitteredSleepMs));
    }
  }
}

async function main() {
  console.log(pc.bold("\n=== Enterprise Retry with Full Jitter & Live OpenAI ==="));
  console.log(pc.dim("Demonstrating exponential backoff and jitter under transient errors and injection after 2 attempts...\n"));

  let openaiClient: OpenAI | null = null;
  try {
    openaiClient = getOpenAIClient();
  } catch (err: any) {
    console.log(pc.yellow(`⚠️  OpenAI client not configured: ${err.message}`));
  }

  let attemptTracker = 0;

  // Callable function executing live OpenAI calls with dynamic error injection
  const resilientOpenAICall = async (attempt: number): Promise<string> => {
    attemptTracker++;
    console.log(pc.cyan(`\n[Dispatch] Sending request to OpenAI gpt-4o-mini (Execution attempt #${attemptTracker})...`));

    // INJECTION RULE: If after 2 attempts we don't get any error from OpenAI,
    // inject a transient 429 RateLimitError to showcase exponential backoff & full jitter
    if (attemptTracker <= 2) {
      console.log(pc.magenta(`   [Injection Check] Attempt #${attemptTracker}: Simulating transient 429 RateLimitError (no natural error encountered)...`));
      const syntheticErr: any = new Error("429 Too Many Requests: TPM rate limit exceeded (Simulated provider transient error)");
      syntheticErr.status = 429;
      syntheticErr.name = "RateLimitError";
      throw syntheticErr;
    }

    if (!openaiClient) {
      return "200 OK: Fallback simulation response (OpenAI client not initialized)";
    }

    // Live call to OpenAI model
    const response = await openaiClient.chat.completions.create({
      model: "gpt-4o-mini",
      messages: [
        {
          role: "user",
          content: "Explain the benefit of exponential backoff with full jitter in telecom API gateways in 1 concise sentence.",
        },
      ],
      max_tokens: 60,
      temperature: 0.2,
    });

    const reply = response.choices[0]?.message?.content?.trim() || "";
    return `200 OK (${response.model}): "${reply}"`;
  };

  try {
    const result = await retryWithFullJitter(resilientOpenAICall, {
      maxRetries: 4,
      baseBackoffMs: 400,
      maxBackoffMs: 3000,
    });
    console.log(pc.green(`\n✔ Final Success: ${result}\n`));
  } catch (err: any) {
    console.log(pc.red(`\n✘ Exhausted all retry attempts: ${err.message}\n`));
  }
}

if (process.argv[1]?.includes("retryWithJitter")) {
  main().catch(console.error);
}
