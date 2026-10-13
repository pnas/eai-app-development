# Lab 02: Prompt Cache Optimization & Audit

## Problem Statement
Your customer support triage agent processes 50,000 tickets daily across Anthropic, OpenAI, and Google Gemini models. Your team enabled Prompt Caching, expecting an 80% to 90% cost reduction on system instructions and product manuals.

However, your monthly billing dashboard shows:
- **Cache Read Tokens: 0**
- **Cache Write Tokens: 50,000,000**
- **Effective Cost Savings: $0.00**

You have been tasked with auditing the prompt assembly pipeline, identifying why prompt cache hits are failing, and refactoring the pipeline to achieve $\ge 90\%$ cache hit rates across providers.

---

## The 5 Underlying Defects to Fix

1. **Prefix Mutation via Timestamp Injection**:
   The prompt builder prepends `Current time: <isoformat>` at index 0. Because prefix caching relies on cryptographic hashing from token 0 onwards, changing line 1 invalidates the entire cache tree on every single request.
2. **Unstable JSON Serialization**:
   Tool schemas and system parameters are serialized with non-deterministic dictionary key ordering (`json.dumps(obj)` without `sort_keys=True`).
3. **Sub-Threshold Payload Size**:
   Different providers enforce distinct minimum token thresholds:
   - **Anthropic**: Requires a minimum of **1,024 tokens** (Claude Opus 5/5.5, Claude Sonnet 5/5.5, Claude 3.7 Sonnet, Claude 3.5 Sonnet, Claude 3 Opus) or **2,048 tokens** (Claude Haiku 5.5, Claude 3.5 Haiku, Claude 3 Haiku). Note: Document citations caching and mid-conversation system messages are supported.
   - **OpenAI**: Requires $\ge$ **1,024 tokens** for automatic prefix caching (matching in **128-token increments**).
   - **Google Gemini (Enterprise Agent Platform)**:
     - **Gemini 2 family** (e.g., Gemini 2.5 Flash / Pro): **2,048 tokens** minimum for both implicit and explicit caching.
     - **Gemini 3 family**: **4,096 tokens** minimum (or **6,144 tokens** for implicit caching on Gemini 3.0 Flash Preview, 3.1 Pro Preview, 3.7 Flash, and 3.8 Flash).
   If a prompt payload falls below the model's threshold, it is ignored by the cache engine.
4. **Incorrect Breakpoint Placement**:
   For Anthropic, `{"type": "ephemeral"}` was attached to the dynamic user ticket message instead of the static knowledge base block.
5. **Breakpoint Exhaustion & Lookback Window**:
   - Anthropic restricts requests to a maximum of **4 cache breakpoints** (`{"type": "ephemeral"}`) per call across system, tools, and message history. Exceeding 4 yields an API error.
   - **Top-Level Automatic Caching**: Placing `cache_control: {"type": "ephemeral"}` at the request body root automatically targets the last cacheable block and moves forward with each turn. When mixed with explicit breakpoints, top-level automatic caching consumes 1 of the 4 available breakpoint slots.
   - **20-Block Lookback Window**: Anthropic walks backward at most 20 blocks looking for an entry prior requests wrote (with consecutive `tool_use`/`tool_result` blocks counting as 1 position). If a turn introduces $\ge 20$ blocks, intermediate explicit breakpoints prevent lookback exhaustion.
   - **Extended 1-Hour TTL**: Anthropic supports `{"type": "ephemeral", "ttl": "1h"}` at 2.0x write price (vs. default 5-min rolling TTL at 1.25x write price).
6. **Automated Cache Miss Diagnostics**:
   Without telemetry inspection, pipeline regressions go unnoticed.
   - **Anthropic Cache Diagnostics**: Passing `diagnostics: {"previous_message_id": ...}` attributes misses to `system_changed`, `tools_changed`, `messages_changed`, `model_changed`, `previous_message_not_found`, or `unavailable`, and estimates `cache_missed_input_tokens`.
   - **OpenAI Cache Diagnostics**: Passing `prompt_cache_options.comparison_response_id` attributes misses to `model_changed`, `prompt_cache_key_changed`, `reasoning_effort_changed`, `tools_changed`, or `input_changed`.

---

## Provider Comparison Matrix

| Provider & Model Family | Caching Strategy | Min Tokens | Granularity | Read Discount | Write / Storage Cost | TTL Options |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Anthropic Claude 3.7 / 3.5** | Explicit Breakpoints & Top-Level Automatic | 1,024 (Sonnet/Opus) / 2,048 (Haiku) | Block / 20-block lookback (max 4 slots) | **90% off** (0.10x) <br> *(0.05x Sonnet 5.5, 0.025x Mythos)* | 1.25x base write (5m) <br> 2.0x base write (1h) | **5-min** rolling default <br> **1-hour** extended (`ttl: "1h"`) |
| **OpenAI GPT-4o / o-series** | Automatic Prefix Matching | 1,024 tokens | 128-token blocks | **50% off read** (0.50x) | Standard input price (100% / 0% surcharge) | Dynamic cluster LRU (5-60 min) |
| **OpenAI GPT-5.6+ / GPT-6 / GPT-6.1 Sol** | Dual-Mode: Explicit Breakpoints (max 4) or Implicit | 1,024 tokens | Block / Message | **90% - 95% off read** (0.10x / 0.05x Sol) | 125% write surcharge (30-min rolling TTL) | 30-min rolling TTL (`ttl: "30m"`) |
| **Google Gemini 2.5+** | **Implicit Caching** (Default on GCP) | 2,048 tokens (Gemini 2) / 4,096 tokens (Gemini 3) | Exact prefix | **90% off read** (0.10x) | **$0.00 storage fee** | Dynamic LRU |
| **Google Gemini 2.5+** | **Explicit Caching** (`CachedContent`) | 2,048 tokens (Gemini 2) / 4,096 tokens (Gemini 3) | CachedContent resource | **90% off read** (75% on Gemini 2.0) | Standard input write + hourly TTL storage | Configurable TTL (1m to indefinite) |

---

## Agentic Security & Isolation Rules (Google Gemini Enterprise)

When auditing and designing agentic pipelines:
- **Project Isolation**: Google Cloud isolates context caches by GCP project number; caches are never shared across projects.
- **Multi-Tenant Context Scoping**: In agentic proxy workflows, scope cached agent outputs and prompt context strictly to each execution context to prevent credentials or sensitive session data from leaking across end users.
- **VPC Service Controls**: Google Gemini context caching supports VPC-SC service perimeters; ensure Cloud Storage cache sources are within the perimeter.

---

## Instructions

### Python
- Starter code: `python/starter.py`
- Reference solution: `python/solution.py`
- Implement:
  - `OptimizedPromptBuilder.build_optimized_payload()`
  - `OptimizedPromptBuilder.is_anthropic_cache_eligible()`
  - `OptimizedPromptBuilder.is_openai_cache_eligible()`
  - `OptimizedPromptBuilder.count_anthropic_breakpoints()`
  - `OptimizedPromptBuilder.is_gemini_cache_eligible()`
  - `OptimizedPromptBuilder.diagnose_cache_miss()`
- Run tests:
  ```powershell
  python/.venv/Scripts/pytest exercises/lab02_prompt_cache_audit/python/test_cache_audit.py
  ```

### TypeScript
- Starter code: `typescript/starter.ts`
- Reference solution: `typescript/solution.ts`
- Implement:
  - `OptimizedPromptBuilder.buildOptimizedPayload()`
  - `OptimizedPromptBuilder.isAnthropicCacheEligible()`
  - `OptimizedPromptBuilder.isOpenAICacheEligible()`
  - `OptimizedPromptBuilder.countAnthropicBreakpoints()`
  - `OptimizedPromptBuilder.isGeminiCacheEligible()`
  - `OptimizedPromptBuilder.diagnoseCacheMiss()`
- Run tests:
  ```powershell
  npx tsx --test ../exercises/lab02_prompt_cache_audit/typescript/testCacheAudit.ts
  ```

