# Student Hands-on Engineering Labs

Welcome to the hands-on laboratory exercises for **Production GenAI API Integrations**. These labs simulate real-world production engineering challenges where naive implementations fail under scale, cost, or network pressure.

---

## Lab Directory

| Lab | Name | Core Concepts | Language Stacks |
| :--- | :--- | :--- | :--- |
| **Lab 01** | [Token Bucket Rate Limiter & Jittered Retry](./lab01_rate_limiter) | Leaky/Token Bucket, Proactive Quota Throttling, Decorrelated Jitter | Python (`uv`) & TypeScript (`tsx`) |
| **Lab 02** | [Prompt Cache Optimization Audit](./lab02_prompt_cache_audit) | Prefix Invalidation, Dynamic Timestamps, Threshold Sizing | Python (`uv`) & TypeScript (`tsx`) |
| **Lab 03** | [Multi-Provider Resilience Cascade](./lab03_resilience_cascade) | Circuit Breaker State Machine, Automated Failover, Fallback Quality | Python (`uv`) & TypeScript (`tsx`) |
| **Lab 04** | [Batch API Cost Arbitrage Pipeline](./lab04_batch_pipeline) | JSONL Batch Construction, Line Error Handling, 50% Cost Savings | Python (`uv`) & TypeScript (`tsx`) |

---

## How to Work on the Labs

Each lab contains:
1. `README.md`: Problem statement, business scenario, mathematical constraints, and instructions.
2. `python/starter.py` & `typescript/starter.ts`: Starter code with `TODO` markers and failing placeholder logic.
3. `python/solution.py` & `typescript/solution.ts`: Reference solution implementing the full architecture.
4. `test_...`: Automated test suites that verify correctness, concurrency safety, and edge cases.

### Running Tests in Python
```powershell
cd python
# Test the starter (should fail until you fix it)
uv run pytest ../exercises/lab01_rate_limiter/python/test_rate_limiter.py

# Test your implementation or check the reference solution
uv run pytest ../exercises/lab01_rate_limiter/python/test_rate_limiter.py -k "test_solution"
```

### Running Tests in TypeScript
```powershell
cd typescript
# Run node's built-in test runner with tsx
npx tsx --test ../exercises/lab01_rate_limiter/typescript/testRateLimiter.ts
```

