/**
 * Lab 03 TypeScript Starter: Multi-Provider Fallback Cascade with Circuit Breakers.
 */

export enum CircuitState {
  CLOSED = "CLOSED",
  OPEN = "OPEN",
  HALF_OPEN = "HALF_OPEN",
}

export class CircuitBreaker {
  public state: CircuitState = CircuitState.CLOSED;
  public failureCount = 0;
  private lastStateChange = Date.now();

  constructor(
    public readonly failureThreshold = 3,
    public readonly recoveryTimeoutMs = 30000
  ) {}

  public allowRequest(): boolean {
    if (this.state === CircuitState.OPEN) {
      const now = Date.now();
      if (now - this.lastStateChange > this.recoveryTimeoutMs) {
        this.state = CircuitState.HALF_OPEN;
        this.lastStateChange = now;
        return true;
      }
      return false;
    }
    return true;
  }

  public recordSuccess(): void {
    this.failureCount = 0;
    this.state = CircuitState.CLOSED;
  }

  public recordFailure(): void {
    this.failureCount++;
    if (this.failureCount >= this.failureThreshold) {
      this.state = CircuitState.OPEN;
      this.lastStateChange = Date.now();
    }
  }
}

export interface ProviderTarget {
  name: string;
  caller: (prompt: string) => Promise<any>;
  breaker?: CircuitBreaker;
}

export class FallbackCascade {
  constructor(public readonly providers: ProviderTarget[]) {
    for (const p of this.providers) {
      if (!p.breaker) {
        p.breaker = new CircuitBreaker();
      }
    }
  }

  public async execute(prompt: string): Promise<{
    servedBy: string;
    result: any;
    cascadeDepth: number;
    bypassedProviders: string[];
  }> {
    // TODO:
    // 1. Iterate through this.providers
    // 2. Check provider.breaker!.allowRequest(); if false, collect and bypass
    // 3. Try provider.caller(prompt)
    // 4. On success: recordSuccess, return { servedBy, result, cascadeDepth, bypassedProviders }
    // 5. On error:
    //    If error is 400 Bad Request, rethrow immediately (do NOT fallback)
    //    Otherwise recordFailure on breaker and try next provider
    // 6. If all fail, throw Error("All providers exhausted in cascade")
    throw new Error("TODO: Implement FallbackCascade.execute");
  }
}

