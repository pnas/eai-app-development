# Lab 01: Token-Bucket Rate Limiter & Decorrelated Jitter

## Problem Statement
In production, your GenAI microservice experiences traffic spikes during marketing campaigns. When hundreds of users hit the service simultaneously, your upstream LLM provider responds with cascading `HTTP 429 Too Many Requests`.

Relying solely on reactive retries is insufficient: simultaneous retries create a **thundering herd**, exacerbating cluster congestion and wasting compute.

## Objective
Implement a client-side **proactive Token-Bucket Rate Limiter** and a **Decorrelated Jitter Backoff** algorithm.

### Key Requirements
1. **Token Bucket Algorithm**:
   - Bucket holds up to `capacity` tokens.
   - Refills smoothly at `refill_rate` tokens per second.
   - `acquire(tokens)`: Blocks asynchronously until requested tokens are available.
   - Concurrency safe: Multiple parallel requests must not overdraw the bucket.

2. **Decorrelated Jitter Calculation**:
   - Formula: $T_{next} = \min(T_{max}, \text{Uniform}(T_{base}, T_{prev} \times 3))$
   - Prevents synchronized retry waves across distributed worker nodes.

3. **Resilient Request Execution**:
   - Wrap an LLM call: acquire capacity before sending, catch HTTP 429, and retry using calculated jittered delay up to `max_retries`.

---

## Provider Rate Limiting Headers & Telemetry

When designing production rate limiters, client-side proactive rate limiting works hand-in-hand with provider telemetry headers:

| Provider | TPM / RPM Limits | Key HTTP Response Headers | Documentation Reference |
| :--- | :--- | :--- | :--- |
| **OpenAI** | Tiered 1–5 based on payment history;<br/>`slow_down` 429 for temporary spikes;<br/>Fast Mode ramp: 1M TPM baseline (+50% per 15m) | `x-ratelimit-limit-requests`<br/>`x-ratelimit-remaining-requests`<br/>`x-ratelimit-reset-requests`<br/>`x-ratelimit-limit-tokens`<br/>`x-ratelimit-remaining-tokens`<br/>`x-ratelimit-reset-tokens`<br/>`retry-after` | [OpenAI Rate Limits Guide](https://developers.openai.com/api/docs/guides/rate-limits)<br/>[Fast Mode Guide](https://developers.openai.com/api/docs/guides/fast-mode) |
| **Anthropic** | Tiered 1–4 based on deposit balance | `anthropic-ratelimit-requests-limit`<br/>`anthropic-ratelimit-requests-remaining`<br/>`anthropic-ratelimit-requests-reset`<br/>`anthropic-ratelimit-tokens-limit`<br/>`anthropic-ratelimit-tokens-remaining`<br/>`retry-after` | [Anthropic Rate Limits Documentation](https://docs.anthropic.com/en/api/rate-limits) |
| **Google Gemini** | Project quota in Google Cloud Console / AI Studio (e.g. `gemini-3.8-flash`, `gemini-3.5-flash-lite`) | Standard Cloud Quota headers<br/>`retry-after` on HTTP 429 | [Gemini Rate Limits](https://ai.google.dev/gemini-api/docs/rate-limits)<br/>[Gemini Models](https://ai.google.dev/gemini-api/docs/models) |

### Engineering Architecture: Dual-Layer Resilience
1. **Layer 1: Proactive Token Bucket (Client-Side)**
   Prevents unnecessary network traffic by smoothing out bursts before requests leave your infrastructure.
2. **Layer 2: Reactive Decorrelated Jitter + Retry-After (Server-Side)**
   If a request breaches upstream concurrency or token quotas, inspect the `retry-after` header if provided; otherwise, calculate next backoff delay using decorrelated jitter:
   $$T_{next} = \min(T_{max}, \text{Uniform}(T_{base}, T_{prev} \times 3))$$

---

## Instructions

### Python
- Starter code: `python/starter.py`
- Implement the `TODO` sections in `TokenBucket` and `calculate_decorrelated_jitter`.
- Verify with tests:
  ```powershell
  uv run --directory python pytest ../exercises/lab01_rate_limiter/python/test_rate_limiter.py
  ```

### TypeScript
- Starter code: `typescript/starter.ts`
- Implement the `TODO` sections in `TokenBucket` and `calculateDecorrelatedJitter`.
- Verify with tests:
  ```powershell
  npm run test:lab01
  ```
