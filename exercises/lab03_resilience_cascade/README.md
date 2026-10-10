# Lab 03: Multi-Provider Fallback Cascade with Circuit Breakers

## Problem Statement
Relying on a single GenAI provider creates a single point of failure (SPOF). When Anthropic returns `HTTP 529 Overloaded` or OpenAI returns `HTTP 500 Internal Server Error`, waiting for multiple timeouts and retries freezes customer transactions.

## Objective
Implement an autonomous **Multi-Provider Fallback Cascade** integrated with **Circuit Breakers** across 3 providers:
1. **Primary**: Claude 3.7 Sonnet
2. **Secondary**: GPT-4o
3. **Tertiary**: Gemini 1.5 Flash

---

## Architectural Rules

1. **Independent Circuit Breakers**:
   Each provider maintains its own state: `CLOSED` (healthy), `OPEN` (tripped/bypassed), or `HALF_OPEN` (probing).
2. **Fast-Bypass on Open Circuit**:
   If Primary's circuit is `OPEN`, the orchestrator must **bypass Primary instantly** (0ms latency penalty) and route straight to Secondary.
3. **Error Discrimination**:
   - Transient server errors (`500`, `502`, `503`, `504`, `529`) and rate limits (`429`) trigger failover to the next provider and record failures.
   - Client errors (`400 Bad Request`, schema validation errors) MUST NOT trigger failover; they must fail immediately to avoid poisoning downstream providers.
4. **Execution Telemetry**:
   The response must include telemetry detailing the serving provider, latency, and circuit status.

---

## Instructions

### Python
- Starter code: `python/starter.py`
- Implement `FallbackCascade.execute()`
- Run tests:
  ```powershell
  uv run pytest exercises/lab03_resilience_cascade/python/test_cascade.py
  ```

### TypeScript
- Starter code: `typescript/starter.ts`
- Implement `FallbackCascade.execute()`
- Run tests:
  ```powershell
  npx tsx --test exercises/lab03_resilience_cascade/typescript/testCascade.ts
  ```

