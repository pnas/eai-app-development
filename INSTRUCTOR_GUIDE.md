# Instructor & Facilitator Guide: Production GenAI API Integrations

This guide provides instructors, engineering leads, and workshop facilitators with the pedagogical structure, delivery timetable, speaker prompts, live coding benchmarks, and lab grading rubrics for teaching **Production GenAI API Integrations**.

---

## 1. Course Architecture & Delivery Formats

This curriculum is designed for **Senior Software Engineers, Backend Architects, and Tech Leads** moving from toy LLM prototypes to mission-critical, enterprise-grade production services.

### Delivery Options

| Format | Duration | Structure | Recommended Audience |
| :--- | :--- | :--- | :--- |
| **1-Day Intensive** | 8 Hours | 45 min Lecture + 15 min Demo + 20 min Quick Lab per module | Senior Backend / Platform Engineers |
| **2-Day Deep Dive** | 16 Hours | 40 min Lecture + 30 min Code Walkthrough + 45 min Hands-on Lab + 15 min Review | Engineering Teams, Tech Leads, AI Architects |
| **Weekly Masterclass** | 6 Weeks (2h/week) | 1 Module per week (Lecture + Assignment + Weekly Code Review) | Upskilling Teams / Engineering Academies |

---

## 2. 2-Day Workshop Master Schedule

### Day 1: Protocols, Encodings, and Caching Economics

| Time | Topic | Format | Deliverables / Labs |
| :--- | :--- | :--- | :--- |
| **09:00 - 09:30** | Course Kickoff & Environment Setup | Setup | Verify `uv` (Python) and `tsx` (Node.js) environments |
| **09:30 - 10:45** | **Module 1: API Paradigms & Wire Protocols** | Lecture + Code | `01_api_paradigms.md`, SSE streaming inspect, tool calling wire diff |
| **10:45 - 11:00** | *Morning Break* | - | - |
| **11:00 - 12:30** | **Module 2: Structured Outputs & Grammar Engines** | Lecture + Code | `02_structured_outputs.md`, JSON schema grammar logit masking, self-repair |
| **12:30 - 13:30** | *Lunch Break* | - | - |
| **13:30 - 15:00** | **Module 3: Prompt Caching & GPU KV-Cache** | Lecture + Code | `03_prompt_caching_and_kvcache.md`, PagedAttention vs prefix trees |
| **15:00 - 16:30** | **Hands-on Lab 1: Prompt Cache Audit & Optimization** | Hands-on Lab | `exercises/lab02_prompt_cache_audit` (Fixing 6 deadly cache bugs) |
| **16:30 - 17:00** | Day 1 Debrief & Architecture Q&A | Discussion | Whiteboard review of GPU memory vs cloud billing |

### Day 2: Batching, Distributed Resilience, and Gateway Routing

| Time | Topic | Format | Deliverables / Labs |
| :--- | :--- | :--- | :--- |
| **09:00 - 09:15** | Day 1 Recap & Warmup | Discussion | Quick review of prefix caching & schema strictness |
| **09:15 - 10:30** | **Module 4: Asynchronous Batch Inference** | Lecture + Code | `04_batch_inference.md`, 50% discount arbitrage, batch orchestrator |
| **10:30 - 10:45** | *Morning Break* | - | - |
| **10:45 - 12:15** | **Module 5: Resilience, Circuit Breakers & Agent State Recovery** | Lecture + Code | `05_error_handling_resilience.md`, 429 stampedes, Circuit Breakers, LangGraph SQLite checkpointer |
| **12:15 - 13:15** | *Lunch Break* | - | - |
| **13:15 - 14:30** | **Hands-on Lab: Resilience Cascade & Agent Crash Recovery** | Hands-on Lab | `exercises/lab03_resilience_cascade` & `exercises/lab05_langgraph_recovery` |
| **14:30 - 15:45** | **Module 6: Gateways, Dual Telemetry & OpenTelemetry** | Lecture + Code | `06_gateways_and_cost_optimization.md`, LiteLLM proxy, LangSmith + SIEM logging, OTel bridge |
| **15:45 - 16:00** | *Afternoon Break* | - | - |
| **16:00 - 17:00** | Final Capstone Review & Certification | Presentation | Architecture presentations, telemetry dashboards & production checklists |

---

## 3. Module-by-Module Teaching Notes & Speaker Prompts

### Module 1: API Paradigms & Wire Protocols
* **Core Insight**: Model APIs are not standard CRUD endpoints; they are stateful GPU orchestrations wrapped in HTTP.
* **Key Demonstration**:
  - Run `src.m01_paradigms.streaming_comparison` in Python and `chatComparison.ts` in TypeScript.
  - Open browser DevTools or `curl -N` against an SSE stream to show students the `data: [DONE]` sentinel.
* **Whiteboard Prompt**:
  - *"Why did Anthropic introduce the `message_delta` event with `stop_reason` instead of closing the TCP socket?"*
  - Answer: The TCP connection stays open for HTTP/2 multiplexing; closing connection per stream ruins latency.

### Module 2: Structured Outputs & Grammar Engines
* **Core Insight**: JSON mode is a prompt trick; Grammar-constrained decoding is mathematically guaranteed at logit sampling.
* **Common Student Trap**:
  - Putting optional fields in Pydantic/Zod schemas without realizing OpenAI requires `additionalProperties: false` on every object in the tree.
* **Key Demonstration**:
  - Show logit bias masking: When the parser expects a colon `:` after a key, tokens like `"apple"`, `"true"`, or `123` have their probability set to $-\infty$.
  - Demonstrate `src.m02_structured_outputs.self_repair`: What happens when an older model (or local model) produces truncated JSON.

### Module 3: Prompt Caching & GPU KV-Cache
* **Core Insight**: Understand the difference between hardware PagedAttention inside vLLM/TensorRT-LLM and prefix hashing in cloud APIs.
* **Teaching Analogy**:
  - Prompt cache is like a Git commit hash tree: changing 1 character at the beginning invalidates all child commits. Changing a character at the very end preserves 99% of the cache.
* **The 6 Deadly Sins Drill**:
  - Ask students to find the bug in this snippet:
    ```python
    prompt = f"Today is {datetime.now().isoformat()}.\n" + SYSTEM_DOCUMENTATION
    ```
  - Ask why putting the dynamic date at line 1 burns 100% of their prompt caching budget.

### Module 4: Asynchronous Batch Inference
* **Core Insight**: Real-time APIs are for humans; Batch APIs are for data pipelines. Leaving offline workloads on synchronous endpoints wastes 50% of the entire GenAI budget.
* **Architecture Discussion**:
  - The SLA trade-off: 24-hour SLA vs real-world turnaround (usually 5 to 45 minutes).
  - Why line-level failure isolation in JSONL is superior to transactional all-or-nothing batching.

### Module 5: Error Taxonomy, Circuit Breakers & Stateful Agent Recovery
* **Core Insight**: Standard exponential backoff causes synchronized herds ("the thundering herd") that kill struggling upstream providers. Full jitter or decorrelated jitter is mandatory.
* **Live Experiment**:
  - Run `src.m05_resilience.circuit_breaker`.
  - Simulate 5 consecutive 503 errors and watch the circuit breaker trip to `OPEN` state, instantly fast-failing traffic without saturating the upstream socket pool.
* **Agent State Persistence Insight**:
  - Contrast ephemeral memory with durable state: what happens if the worker process restarts mid-flight during a 10-step agent loop?
  - Demonstrate `src.langchain_suite.agent_recovery.recover_demo`: showing how a process interrupted during tool calling seamlessly recovers from SQLite checkpointer (`SqliteSaver`) using `thread_id` without re-running earlier steps.

### Module 6: Gateways, Unit Economics & Dual Telemetry (LangSmith + SIEM + OTel)
* **Core Insight**: Direct SDK imports create vendor lock-in; gateways provide proxy routing, but internal agent loops remain opaque unless instrumented with dual telemetry.
* **The Dual Telemetry Architecture**:
  - **LangSmith**: Visual RunTree graphs, prompt evaluation datasets, and latency percentiles for AI engineers.
  - **Structured JSON Logging**: In-band synchronous NDJSON logs for SecOps, SIEM (Splunk/Datadog/CloudWatch), and 1–7 year immutable audit compliance.
  - **OpenTelemetry Bridge**: OTel GenAI Semantic Conventions (`gen_ai.system`, `gen_ai.request.model`, `gen_ai.usage.prompt_tokens`) exported to OTel Collector & APMs.
* **Edge PII Redaction Demo**:
  - Demonstrate `PIIScrubber` masking emails, phone numbers, and bearer credentials *before* logs leave process memory.

---

## 4. Student Lab Assignments & Rubric

The `exercises/` directory contains five production engineering challenges:

1. **Lab 1: Token-Bucket Rate Limiter & Jittered Backoff (`exercises/lab01_rate_limiter`)**
   - **Goal**: Implement a proactive token bucket in client code that enforces RPM/TPM limits and decorrelated jitter backoff.
   - **Passing Criteria**: Passes all tests in `test_rate_limiter.py` / `testRateLimiter.ts`.

2. **Lab 2: Prompt Cache Auditor (`exercises/lab02_prompt_cache_audit`)**
   - **Goal**: Audit a broken prompt assembly pipeline that suffers from timestamp injection, unstable JSON serialization, and sub-threshold blocks, refactoring it to guarantee >90% cache hits.
   - **Passing Criteria**: Passes all tests in `test_cache_audit.py` / `testCacheAudit.ts`.

3. **Lab 3: 3-Tier Multi-Provider Fallback Cascade (`exercises/lab03_resilience_cascade`)**
   - **Goal**: Build an autonomous fallback pipeline that tries Anthropic Sonnet, fails over to OpenAI GPT-4o, and falls back to Google Gemini Flash with circuit breaker isolation.
   - **Passing Criteria**: Passes all tests in `test_cascade.py` / `testCascade.ts`.

4. **Lab 4: Batch API Cost Arbitrage Orchestrator (`exercises/lab04_batch_pipeline`)**
   - **Goal**: Ingest 1,000 synthetic records, format compliant JSONL payloads, handle partial failure responses, and output an audited cost reduction report.
   - **Passing Criteria**: Passes all tests in `test_batch.py` / `testBatch.ts`.

5. **Lab 5: Fault-Tolerant State Machine & SQLite Crash Recovery (`exercises/lab05_langgraph_recovery`)**
   - **Goal**: Build an autonomous LangGraph agent state machine with tool execution, SQLite checkpoint persistence, and process crash recovery that resumes unfinished threads without duplicating side effects.
   - **Passing Criteria**: Passes all tests in `test_recovery.py` / `testRecovery.ts`.

---

## 5. Slide Presentation Compilation

To render the presentation slides into interactive HTML slide decks:

```powershell
# Using the automated build script:
.\scripts\build_slides.ps1

# Or run Marp directly:
npx @marp-team/marp-cli slides/ -o dist/slides/ --html
```

