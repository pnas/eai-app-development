import pc from "picocolors";

export enum BreakerState {
  CLOSED = "CLOSED",
  OPEN = "OPEN",
  HALF_OPEN = "HALF_OPEN",
}

export class CircuitBreakerOpenException extends Error {
  constructor(message: string) {
    super(message);
    this.name = "CircuitBreakerOpenException";
  }
}

export class CircuitBreaker {
  public name: string;
  public failureThreshold: number;
  public recoveryTimeoutMs: number;

  public state: BreakerState = BreakerState.CLOSED;
  public failureCount: number = 0;
  public lastStateChange: number = Date.now();

  constructor(name: string, failureThreshold: number = 3, recoveryTimeoutMs: number = 5000) {
    this.name = name;
    this.failureThreshold = failureThreshold;
    this.recoveryTimeoutMs = recoveryTimeoutMs;
  }

  beforeCall() {
    const now = Date.now();
    if (this.state === BreakerState.OPEN) {
      const elapsed = now - this.lastStateChange;
      if (elapsed >= this.recoveryTimeoutMs) {
        this.state = BreakerState.HALF_OPEN;
        this.lastStateChange = now;
        console.log(pc.yellow(`[Breaker: ${this.name}] Transitioning to HALF_OPEN (Allowing single probe request)`));
      } else {
        const remainingSec = ((this.recoveryTimeoutMs - elapsed) / 1000).toFixed(1);
        throw new CircuitBreakerOpenException(
          `Circuit breaker '${this.name}' is OPEN. Fast-failing request (cool-off: ${remainingSec}s remaining).`
        );
      }
    }
  }

  recordSuccess() {
    if (this.state !== BreakerState.CLOSED) {
      console.log(pc.green(`[Breaker: ${this.name}] Probe succeeded! Resetting to CLOSED state.`));
    }
    this.state = BreakerState.CLOSED;
    this.failureCount = 0;
  }

  recordFailure(error: any) {
    this.failureCount++;
    console.log(pc.yellow(`[Breaker: ${this.name}] Failure recorded (${this.failureCount}/${this.failureThreshold}): ${error?.message || error}`));

    if (this.failureCount >= this.failureThreshold) {
      this.state = BreakerState.OPEN;
      this.lastStateChange = Date.now();
      console.log(pc.red(`[Breaker: ${this.name}] Failure threshold exceeded! Circuit breaker TRIPPED to OPEN.`));
    }
  }
}

async function main() {
  console.log(pc.bold("\n=== Circuit Breaker State Machine Simulation (TypeScript) ===\n"));
  const breaker = new CircuitBreaker("Anthropic_Claude", 3, 2000);

  // Simulate 3 failures
  for (let i = 1; i <= 3; i++) {
    try {
      breaker.beforeCall();
      throw new Error("529 Overloaded: Claude infrastructure capacity reached");
    } catch (err: any) {
      breaker.recordFailure(err);
    }
  }

  // 4th call should fast-fail
  console.log(pc.cyan("\nAttempting 4th call while breaker is OPEN:"));
  try {
    breaker.beforeCall();
  } catch (err: any) {
    console.log(pc.red(`FAST-FAIL CAUGHT: ${err.message}`));
  }

  // Wait for cool-off
  console.log(pc.gray("\nWaiting 2.5s for cool-off timeout..."));
  await new Promise((r) => setTimeout(r, 2500));

  try {
    breaker.beforeCall();
    console.log(pc.cyan("Probe call allowed. Simulating provider recovery..."));
    breaker.recordSuccess();
  } catch (err: any) {
    console.log(pc.red(`Probe failed: ${err.message}`));
  }
}

main().catch(console.error);

