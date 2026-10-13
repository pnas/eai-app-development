# TypeScript Examples: Advanced GenAI API Integration

Production-ready TypeScript implementations for enterprise GenAI integrations targeting **Node.js 24+** (and modern ES Modules). This repository showcases native provider SDKs (`openai`, `@anthropic-ai/sdk`, `@google/genai`), **Zod** compile-time and runtime validation, resilient architectural patterns (circuit breakers, token-bucket rate limiting, fallback cascades), and an enterprise **LangChain / LangGraph** suite.

---

## 🛠️ Setup & Prerequisites

### Requirements
- **Node.js**: v20+ (Node.js 24 recommended)
- **Package Manager**: `npm` v10+
- **TypeScript Runtime**: [`tsx`](https://github.com/privatenumber/tsx) (included in `devDependencies`)

### 1. Install Dependencies
```bash
npm install
```

### 2. Configure Environment Variables
Copy the root `.env.example` (or configure your workspace root `.env`):
```bash
cp .env.example .env
```
Ensure your API keys are provided:
```env
OPENAI_API_KEY=sk-proj-...
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=AIzaSy...
OPENROUTER_API_KEY=sk-or-v1-...  # Optional: For gateway routing
```
> [!NOTE]
> All TypeScript modules use `loadWorkspaceEnv()` which automatically searches parent directories up to the repository root to discover `.env`.

---

## 📂 Module Catalog & Execution Commands

### Module 1: API Paradigms & Wire Protocols
Explores the wire-level mechanics, streaming chunk parsing, and tool calling across OpenAI, Anthropic, and Gemini.

| Script / Topic | Run Command | Description |
| :--- | :--- | :--- |
| **Cross-Provider Chat Comparison** | `npm run start:m01` | Normalized completion across providers with token extraction and latency tracking. |
| **SSE Streaming & Token Usage** | `npm run start:m01:stream` | Server-Sent Events (SSE) streaming with live terminal output and chunk-level usage extraction. |
| **Wire Protocol Tool Calling** | `npm run start:m01:tool` | Cross-provider function calling (`weather`, `telecom diagnostics`) with strict parameter typing. |
| **Reasoning & Extended Thinking** | `npx tsx src/m01_paradigms/responsesReasoningDemo.ts` | Deep reasoning, chain-of-thought extraction, and budget tokens inspection. |

---

### Module 2: The Response API & Structured Outputs
Eliminates brittle regex parsing through grammar-constrained schema decoders and self-healing repair loops.

| Script / Topic | Run Command | Description |
| :--- | :--- | :--- |
| **OpenAI Strict JSON Schema** | `npm run start:m02` | Enforces 100% schema compliance using `zodResponseFormat` with strict schema validation. |
| **Anthropic Forced Tool Choice** | `npm run start:m02:anthropic` | Forces Anthropic models into structured output mode via `tool_choice: { type: "tool" }`. |
| **Google Gemini Response Schema** | `npm run start:m02:gemini` | Constrains Gemini completions to typed JSON via `responseSchema`. |
| **Self-Healing JSON Repair Loop** | `npm run start:m02:repair` | Catches malformed or truncated JSON and feeds syntax errors back to the model for automatic correction. |
| **Anthropic Document Citations** | `npm run start:m02:citations` | Extracts verifiable citations linked directly to cited source document indices. |
| **OpenAI Predicted Outputs** | `npm run start:m02:predicted` | Speculative decoding using predicted output strings to accelerate code edits and structured updates. |

---

### Module 3: Prompt Caching & The KV-Cache
Drastically reduces input token latency and cost (up to 90%) by designing cache-friendly system prompts.

| Script / Topic | Run Command | Description |
| :--- | :--- | :--- |
| **Cache Invalidation Benchmark** | `npm run start:m03` | Demonstrates how volatile timestamps destroy cache hits and how static prefixes preserve cache lines. |
| **Anthropic Ephemeral Breakpoints** | `npm run start:m03:anthropic` | Implements 4-breakpoint rolling prompt cache using `cache_control: { type: "ephemeral" }`. |
| **OpenAI Automatic Prefix Cache** | `npx tsx src/m03_prompt_caching/openaiCache.ts` | Validates automatic 1024-token prefix cache hit behavior on OpenAI models. |
| **Gemini Context Caching** | `npx tsx src/m03_prompt_caching/geminiContextCache.ts` | Demonstrates explicit Google Gemini context caching for large corpus retrieval. |

---

### Module 4: Asynchronous Batch Inference
Leverages asynchronous batch queues for high-throughput, non-urgent workloads with a 50% discount.

| Script / Topic | Run Command | Description |
| :--- | :--- | :--- |
| **Batch Orchestrator State Machine** | `npm run start:m04` | Resilient batch lifecycle with polling backoff, status transitions, and dead-letter queue (DLQ). |
| **OpenAI Batch Pipeline** | `npm run start:m04:openai` | Assembles JSONL files, uploads to `/v1/files`, creates batch jobs, and polls for completion. |
| **Anthropic Message Batches** | `npm run start:m04:anthropic` | Dispatches bulk message batches to Anthropic with completion status polling. |
| **Flexible Concurrency Batcher** | `npm run start:m04:flex` | Concurrency-limited worker pool for batching real-time calls without hitting provider TPM/RPM ceilings. |

---

### Module 5: Resilience, Error Taxonomies & Rate Limiting
Production-grade resilience patterns designed for mission-critical enterprise workloads.

| Script / Topic | Run Command | Description |
| :--- | :--- | :--- |
| **Enterprise Token Rate Limiter (Live)** | `npm run start:m05:tokenlimiter` | **WSO2 Pattern**: Token bucket limiter with pre-flight ceilings, spend quotas, live OpenAI calls, and token reconciliation. |
| **Production Circuit Breaker** | `npm run start:m05` / `npm run start:m05:breaker` | Three-state circuit breaker (`CLOSED` &rarr; `OPEN` &rarr; `HALF_OPEN`) with exponential cooldown. |
| **Multi-Provider Fallback Cascade** | `npm run start:m05:fallback` | Resilient cascade failing over across providers: Anthropic &rarr; OpenAI &rarr; Gemini. |
| **Exponential Backoff with Full Jitter** | `npm run start:m05:retry` | Prevents thundering herd problems during downstream outages using decorrelated jitter. |
| **Cross-Provider Error Taxonomy** | `npm run start:m05:taxonomy` | Maps HTTP 400, 429, 500, and 529 vendor errors into standardized domain exceptions. |

#### Live OpenAI Token Rate Limiter & Governor (`tokenRateLimiter.ts`)
The rate limiter implements enterprise patterns inspired by the [WSO2 LLM Rate Limiting Guide](https://wso2.com/api-platform/learn/llm-rate-limiting/):
1. **Pre-flight Ceilings**: Rejects oversized prompts (`maxPromptTokens`) or completions (`maxCompletionTokens`) before any API dispatch (zero vendor spend).
2. **Token Bucket & TPM Limits**: Enforces token bucket capacity with continuous refill (`refillRateTokensPerSec`) and emits `X-RateLimit-*` and `Retry-After` headers.
3. **Budget Ceiling**: Blocks execution when cumulative financial spend exceeds the allocated tier budget.
4. **Live Model Execution**: Dispatches accepted requests to `gpt-4o-mini`.
5. **Usage Reconciliation**: Reconciles estimated pre-flight reservations against actual `response.usage` reported by OpenAI, returning unused tokens to the bucket balance.

Tested against 6 realistic telecom NOC operational scenarios:
```bash
npm run start:m05:tokenlimiter
```
- **Scenario 1**: SIM 5G SA Provisioning (`SST=1, SD=0x000001` slice check) &rarr; `200 OK`
- **Scenario 2**: BGP Peering Flap Root Cause (AS3320 / AS15169 on Frankfurt IX) &rarr; `200 OK`
- **Scenario 3**: Runaway Syslog Dump (Ceiling Breach: 4600 > 4000 limit) &rarr; `400 Bad Request`
- **Scenario 4**: Unbounded Generation (Completion Breach: 1500 > 1000 limit) &rarr; `400 Bad Request`
- **Scenario 5**: Rapid Burst Surge (SIP 503 emergency trace, bucket capacity drain) &rarr; `200 OK`
- **Scenario 6**: Post-Cooldown Recovery (5G UPF cluster health check after 2.5s refill) &rarr; `200 OK`

---

### Module 6: Enterprise Gateways & Cost Minimization
Orchestrates requests through proxy gateways and implements algorithmic cost routing.

| Script / Topic | Run Command | Description |
| :--- | :--- | :--- |
| **Interactive Cost & ROI Calculator** | `npm run start:m06` | Compares monthly token spend, savings from caching, and cost trade-offs across 15+ models. |
| **OpenRouter Dynamic Gateway** | `npm run start:m06:openrouter` | Dynamic fallback routing through OpenRouter with auto-healing and latency monitoring. |
| **LiteLLM Proxy Client** | `npm run start:m06:litellm` | Interfaces with an enterprise LiteLLM proxy for centralized key management and budget governance. |

---

## 🦜 LangChain Suite & LangGraph Agent Suite

Comprehensive enterprise abstractions built with `@langchain/core`, `@langchain/openai`, `@langchain/anthropic`, and `@langchain/langgraph`.

```bash
# Run the interactive LangChain 6-Paradigm CLI
npm run cli:langchain
```

### LangChain Paradigm Execution
| Paradigm | Run Command | Key Feature |
| :--- | :--- | :--- |
| **Paradigm 1: Unified Chat** | `npm run start:lc:m01` | Unified `ChatOpenAI`, `ChatAnthropic`, and `ChatGoogleGenAI` with streaming callbacks. |
| **Paradigm 2: Structured Output** | `npm run start:lc:m02` | Grammar-enforced output with Zod schemas using `.withStructuredOutput()`. |
| **Paradigm 3: Prompt Caching** | `npm run start:lc:m03` | Injects cache control metadata into LangChain message blocks. |
| **Paradigm 4: Batch Inference** | `npm run start:lc:m04` | High-throughput concurrent execution using `model.batch()` with `maxConcurrency`. |
| **Paradigm 5: Resilience & Fallbacks** | `npm run start:lc:m05` | Declarative multi-provider fallback chains using `primary.withFallbacks([backup])`. |
| **Paradigm 5: Token Rate Limited Chain** | `npm run start:lc:m05:tokenlimiter` | LangChain Runnable wrapping WSO2 token-bucket governor with automatic failover cascades. |
| **Paradigm 6: Dynamic Cost Routing** | `npm run start:lc:m06` | Routes simple queries to economy models and complex reasoning queries to flagship models. |
| **Paradigm 6: Gateway Orchestration** | `npm run start:lc:m06:gateway` | Connects LangChain to proxy endpoints (OpenRouter / LiteLLM) with centralized budget quotas. |
| **Agent Recovery & Checkpoints** | `npm run start:lc:agent` | LangGraph agent with SQLite checkpointing and self-repairing loop. |
| **Dual Telemetry Bridge** | `npm run start:lc:telemetry` | Emits structured JSON logs and maps metrics to OpenTelemetry spans. |

---

## 🖥️ Web Showcase: Frontend Agent & Microservice

Demonstrates two architectural patterns connecting a modern web UI with LangChain / LangGraph tool-calling agents:

- **Pattern A (In-Process Monolith)**: Agent runs directly in the server process.
- **Pattern B (Decoupled Microservice)**: Dedicated Express backend (`agentServer.ts`) runs the agent and streams lifecycle events to the browser using **Server-Sent Events (SSE)**.
- **Extensible Tool Registry**: Built-in `get_current_time` (timezone-aware) and `get_random_quote` (categorized quotes).

```bash
# Run both Backend API (port 3001) and Web App (port 3000):
npm run start:frontend:all

# Or run individual components:
npm run start:frontend:backend  # Starts Agent SSE Server on http://localhost:3001
npm run start:frontend:webapp   # Starts Web App Server on http://localhost:3000
```

---

## 🧪 Automated Testing Suite

The repository includes a comprehensive unit and integration test suite using Node.js's built-in test runner (`node:test` via `tsx --test`).

```bash
# Run Token Rate Limiter tests (including token reconciliation and pre-flight ceilings):
npm run test:tokenlimiter

# Run LangChain 6-paradigm CLI tests:
npm run test:cli

# Run Gateway integration tests:
npm run test:gateways

# Run Frontend Agent and SSE tests:
npm run test:frontend-agent

# Run Structured Logger & OpenTelemetry tests:
npm run test:logger
npm run test:otel

# Run all exercise lab verification suites:
npm run test:lab01
npm run test:lab02
npm run test:lab03
npm run test:lab04
npm run test:lab05
```

---

## 📐 Project Structure

```text
typescript/
├── package.json                   # Scripts, dependencies, and type definitions
├── tsconfig.json                  # TypeScript compiler settings (ES2022, NodeNext)
├── testTokenRateLimiter.ts        # Unit tests for WSO2 rate limiter & token governor
├── testCli.ts                     # Tests for the 6-paradigm LangChain CLI
├── testFrontendAgent.ts           # Tests for agent server, tools, and SSE streams
├── testGateways.ts                # Tests for gateway routing & cost calculators
├── src/
│   ├── m01_paradigms/             # Wire protocols, chat comparisons, streaming, tool calls
│   ├── m02_structured_outputs/    # Zod schemas, OpenAI strict, self-repair, predicted outputs
│   ├── m03_prompt_caching/        # Anthropic breakpoints, OpenAI prefix caching, benchmarks
│   ├── m04_batch_processing/      # Batch orchestrator, DLQ, OpenAI & Anthropic batch APIs
│   ├── m05_resilience/            # Circuit breaker, jitter retry, error taxonomy, tokenRateLimiter
│   ├── m06_gateways/              # Cost calculators, OpenRouter, LiteLLM integrations
│   └── langchain_suite/           # Enterprise LangChain & LangGraph implementations
│       ├── core/                  # Models factory, env loader, telemetry, OpenTelemetry bridge
│       ├── agent_recovery/        # State recovery, SQLite checkpoints, self-healing graph
│       ├── frontend_agent/        # Decoupled agent backend (SSE) and web frontend showcase
│       ├── m01_paradigms/ ... m06_gateways/ # LangChain implementations of all 6 paradigms
│       └── cli.ts                 # Interactive unified CLI runner
```
