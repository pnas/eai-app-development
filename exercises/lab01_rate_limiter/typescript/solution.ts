/**
 * Lab 01 TypeScript Reference Solution: Token Bucket Rate Limiter and Decorrelated Jitter.
 */

export class TokenBucket {
  private capacity: number;
  private refillRatePerSec: number;
  private tokens: number;
  private lastRefill: number;
  private lockPromise: Promise<void> = Promise.resolve();

  constructor(capacity: number, refillRatePerSec: number) {
    this.capacity = capacity;
    this.refillRatePerSec = refillRatePerSec;
    this.tokens = capacity;
    this.lastRefill = Date.now();
  }

  private refill(): void {
    const now = Date.now();
    const elapsedSeconds = (now - this.lastRefill) / 1000.0;
    this.tokens = Math.min(this.capacity, this.tokens + elapsedSeconds * this.refillRatePerSec);
    this.lastRefill = now;
  }

  public async acquire(tokens = 1.0): Promise<number> {
    if (tokens > this.capacity) {
      throw new Error(`Requested tokens (${tokens}) exceeds bucket capacity (${this.capacity})`);
    }

    let totalWaitedSec = 0;

    // Mutex locking pattern in TypeScript promises
    const release = await this.lock();
    try {
      while (true) {
        this.refill();
        if (this.tokens >= tokens) {
          this.tokens -= tokens;
          return totalWaitedSec;
        }

        const missing = tokens - this.tokens;
        const waitMs = Math.ceil((missing / this.refillRatePerSec) * 1000);
        await new Promise((resolve) => setTimeout(resolve, waitMs));
        totalWaitedSec += waitMs / 1000.0;
      }
    } finally {
      release();
    }
  }

  public getAvailableTokens(): number {
    this.refill();
    return this.tokens;
  }

  private lock(): Promise<() => void> {
    let unlock: () => void;
    const nextLock = new Promise<void>((resolve) => {
      unlock = resolve;
    });
    const currentLock = this.lockPromise;
    this.lockPromise = this.lockPromise.then(() => nextLock);
    return currentLock.then(() => unlock);
  }
}

export function calculateDecorrelatedJitter(
  baseDelayMs: number,
  maxDelayMs: number,
  previousDelayMs: number
): number {
  const upperBound = Math.max(baseDelayMs, previousDelayMs * 3.0);
  const jittered = Math.random() * (upperBound - baseDelayMs) + baseDelayMs;
  return Math.min(maxDelayMs, jittered);
}

export async function executeWithResilience<T>(
  apiCall: () => Promise<T>,
  rateLimiter: TokenBucket,
  costTokens = 1.0,
  maxRetries = 3,
  baseDelayMs = 20,
  maxDelayMs = 500
): Promise<T> {
  await rateLimiter.acquire(costTokens);

  let delayMs = baseDelayMs;
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await apiCall();
    } catch (err: any) {
      const isRateLimit =
        err?.status === 429 ||
        err?.statusCode === 429 ||
        String(err?.message || "").includes("429");

      if (!isRateLimit || attempt === maxRetries) {
        throw err;
      }

      delayMs = calculateDecorrelatedJitter(baseDelayMs, maxDelayMs, delayMs);
      await new Promise((resolve) => setTimeout(resolve, delayMs));
      await rateLimiter.acquire(costTokens);
    }
  }

  throw new Error("Exhausted retries");
}

