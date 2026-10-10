/**
 * Lab 03 TypeScript Reference Solution: Multi-Provider Fallback Cascade with Circuit Breakers.
 */

import { CircuitState, CircuitBreaker, ProviderTarget } from "./starter.js";

export { CircuitState, CircuitBreaker, ProviderTarget };

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
    const bypassedProviders: string[] = [];
    const errors: string[] = [];

    for (let i = 0; i < this.providers.length; i++) {
      const provider = this.providers[i];

      // 1. Check circuit breaker state
      if (!provider.breaker!.allowRequest()) {
        bypassedProviders.push(provider.name);
        errors.push(`${provider.name}: Circuit OPEN`);
        continue;
      }

      // 2. Attempt invocation
      try {
        const result = await provider.caller(prompt);
        provider.breaker!.recordSuccess();
        return {
          servedBy: provider.name,
          result,
          cascadeDepth: i + 1,
          bypassedProviders,
        };
      } catch (err: any) {
        // 3. Client errors (400) should never fallback
        const isClientError =
          err?.status === 400 ||
          err?.statusCode === 400 ||
          String(err?.message || "").includes("400");

        if (isClientError) {
          throw err;
        }

        // 4. Record transient failure in breaker
        provider.breaker!.recordFailure();
        errors.push(`${provider.name}: ${err.message}`);
      }
    }

    throw new Error(`All providers exhausted in cascade. Errors: ${errors.join("; ")}`);
  }
}

