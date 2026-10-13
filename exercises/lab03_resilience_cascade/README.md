# Lab 03: Multi-Provider Fallback Cascade with Circuit Breakers

## Problem Statement
Relying on a single GenAI provider creates a single point of failure (SPOF). When Anthropic returns `HTTP 529 Overloaded` or OpenAI returns `HTTP 500 Internal Server Error`, waiting for multiple timeouts and retries freezes customer transactions.

## Objective
Implement an autonomous **Multi-Provider Fallback Cascade** integrated with **Circuit Breakers** across 3 providers:
1. **Primary**: Claude Sonnet 5.5 (or Claude 3.7 Sonnet)
2. **Secondary**: OpenAI GPT-5.6 (or GPT-4o)
3. **Tertiary**: Google Gemini 2.5 Flash (or Gemini 1.5 Flash)

---

## Architectural Rules

1. **Independent Circuit Breakers**:
   Each provider maintains its own state: `CLOSED` (healthy), `OPEN` (tripped/bypassed), or `HALF_OPEN` (probing).
2. **Fast-Bypass on Open Circuit**:
   If Primary's circuit is `OPEN`, the orchestrator must **bypass Primary instantly** (0ms latency penalty) and route straight to Secondary.
3. **Error Discrimination & Provider Taxonomy**:
   - Transient server errors (`500 Internal Error`, `502 Bad Gateway`, `503 Service Unavailable`, `504 Gateway Timeout`, `529 Anthropic Overloaded`) and rate limits (`429 Too Many Requests`) trigger failover to the next provider and increment failure counters.
   - For OpenAI specifically, handle `slow_down` (server-side capacity throttling, distinct from standard quota exhaustion), `server_is_overloaded` (HTTP 503), and `resource_unavailable` (HTTP 503 during region failovers).
   - Parse `retry-after` headers on `429` / `503` before scheduling fallback probes.
   - Client errors (`400 Bad Request`, `422 Unprocessable Entity`, schema validation errors) MUST NOT trigger failover; they must fail immediately to avoid poisoning downstream providers.
4. **Execution Telemetry**:
   The response must include telemetry detailing the serving provider, latency, and circuit status.

---

## Reference Documentation
- [OpenAI Rate Limits & Concurrency Guide](https://developers.openai.com/api/docs/guides/rate-limits)
- [OpenAI Latency Optimization Guide](https://developers.openai.com/api/docs/guides/latency-optimization)

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

