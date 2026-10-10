# Lab 02: Prompt Cache Optimization & Audit

## Problem Statement
Your customer support triage agent processes 50,000 tickets daily. Your team enabled Anthropic and OpenAI Prompt Caching, expecting an 80% cost reduction on system instructions and product manuals.

However, your monthly billing dashboard shows:
- **Cache Read Tokens: 0**
- **Cache Write Tokens: 50,000,000**
- **Effective Cost Savings: $0.00**

You have been tasked with auditing the prompt assembly pipeline, identifying why prompt cache hits are failing, and refactoring the pipeline to achieve $\ge 90\%$ cache hit rates.

---

## The 4 Underlying Defects to Fix

1. **Prefix Mutation via Timestamp Injection**:
   The prompt builder prepends `Current time: <isoformat>` at index 0. Because prefix caching relies on cryptographic hashing from token 0 onwards, changing line 1 invalidates the entire cache tree on every single request.
2. **Unstable JSON Serialization**:
   Tool schemas and system parameters are serialized with non-deterministic dictionary key ordering (`json.dumps(obj)` without `sort_keys=True`).
3. **Sub-Threshold Payload Size**:
   Anthropic requires a minimum of **1,024 tokens** (Claude Sonnet) before caching activates. The company's manual is only ~500 tokens, so requests are rejected by the caching engine.
4. **Incorrect Breakpoint Placement**:
   For Anthropic, `{"type": "ephemeral"}` was attached to the dynamic user ticket message instead of the static knowledge base block.

---

## Instructions

### Python
- Starter code: `python/starter.py`
- Implement `PromptCacheAuditor.build_optimized_payload()`
- Run tests:
  ```powershell
  uv run pytest exercises/lab02_prompt_cache_audit/python/test_cache_audit.py
  ```

### TypeScript
- Starter code: `typescript/starter.ts`
- Implement `buildOptimizedPayload()`
- Run tests:
  ```powershell
  npx tsx --test exercises/lab02_prompt_cache_audit/typescript/testCacheAudit.ts
  ```

