# Lab 01: Token-Bucket Rate Limiter & Decorrelated Jitter

## Problem Statement
In production, your GenAI microservice experiences traffic spikes during marketing campaigns. When 200 users hit the service simultaneously, your upstream LLM provider responds with cascading `HTTP 429 Too Many Requests`.

Relying solely on reactive retries is insufficient: 200 simultaneous retries create a **thundering herd**, exacerbating cluster congestion and wasting compute.

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

## Instructions

### Python
- Starter code: `python/starter.py`
- Implement the `TODO` sections in `TokenBucket` and `decorrelated_jitter_delay`.
- Verify with tests:
  ```powershell
  uv run pytest exercises/lab01_rate_limiter/python/test_rate_limiter.py
  ```

### TypeScript
- Starter code: `typescript/starter.ts`
- Implement the `TODO` sections in `TokenBucket` and `calculateDecorrelatedJitter`.
- Verify with tests:
  ```powershell
  npx tsx --test exercises/lab01_rate_limiter/typescript/testRateLimiter.ts
  ```

