/**
 * Module 5: Exponential Backoff with Full Jitter (TypeScript).
 *
 * Prevents the "Thundering Herd" problem by introducing randomness:
 * sleep = Math.random() * Math.min(maxBackoffMs, baseBackoffMs * (2 ** attempt))
 */

import pc from "picocolors";

export interface RetryOptions {
  maxRetries?: number;
  baseBackoffMs?: number;
  maxBackoffMs?: number;
  retryableErrors?: string[];
}

export async function retryWithFullJitter<T>(
  fn: () => Promise<T>,
  options: RetryOptions = {}
): Promise<T> {
  const maxRetries = options.maxRetries ?? 3;
  const baseBackoffMs = options.baseBackoffMs ?? 500;
  const maxBackoffMs = options.maxBackoffMs ?? 4000;

  let attempt = 0;

  while (true) {
    try {
      return await fn();
    } catch (err: any) {
      attempt++;
      if (attempt > maxRetries) {
        console.log(pc.red(`Exceeded max retries (${maxRetries}). Rethrowing error.`));
        throw err;
      }

      // Full Jitter formula
      const ceiling = Math.min(maxBackoffMs, baseBackoffMs * Math.pow(2, attempt));
      const jitteredSleepMs = Math.floor(Math.random() * ceiling);

      console.log(
        pc.yellow(
          `Attempt ${attempt} failed (${err.name || "Error"}: ${err.message}). ` +
          `Backing off with Full Jitter: ${jitteredSleepMs}ms (ceiling: ${ceiling}ms)...`
        )
      );

      await new Promise((resolve) => setTimeout(resolve, jitteredSleepMs));
    }
  }
}

async function main() {
  console.log(pc.bold("\n=== Simulating Retry with Full Jitter (TypeScript) ===\n"));
  let callCount = 0;

  const flakyApiCall = async (): Promise<string> => {
    callCount++;
    console.log(pc.cyan(`Calling downstream LLM endpoint (invocation #${callCount})...`));
    if (callCount < 3) {
      const err: any = new Error("429 Too Many Requests: Rate limit exceeded");
      err.status = 429;
      throw err;
    }
    return "200 OK: Response delivered successfully from Claude Haiku 5.5";
  };

  try {
    const result = await retryWithFullJitter(flakyApiCall, {
      maxRetries: 4,
      baseBackoffMs: 300,
      maxBackoffMs: 2000,
    });
    console.log(pc.green(`\n✔ Result: ${result}\n`));
  } catch (err: any) {
    console.log(pc.red(`\n✘ Final failure: ${err.message}\n`));
  }
}

if (process.argv[1]?.includes("retryWithJitter")) {
  main().catch(console.error);
}
