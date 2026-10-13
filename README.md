# Advanced GenAI Integration: Enterprise Engineering Masterclass

[![Python 3.12](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://python.org)
[![uv](https://img.shields.io/badge/managed%20by-uv-purple.svg)](https://docs.astral.sh/uv/)
[![TypeScript 5](https://img.shields.io/badge/TypeScript-5.x-blue.svg)](https://www.typescriptlang.org/)
[![Node 24](https://img.shields.io/badge/Node-24%2B-green.svg)](https://nodejs.org/)
[![Marp](https://img.shields.io/badge/slides-Marp%20HTML%2FPDF-orange.svg)](https://marp.app/)

An intensive, production-focused engineering curriculum, hands-on laboratory exercises, and dual-stack codebase designed for software engineers and architects building real-world integrations with **OpenAI**, **Anthropic**, and **Google Gemini**.

---

## 🎯 Course Curriculum & Modules

| Module | Title | Core Concepts | Python Code | TypeScript Code |
| :--- | :--- | :--- | :--- | :--- |
| **01** | **[API Paradigms & Protocols](slides/01_api_paradigms.md)** | SDK wire protocols, SSE streaming, content block polymorphism, tool calling wire formats. | `python/src/m01_paradigms/` | `typescript/src/m01_paradigms/` |
| **02** | **[The Response API & Structured Outputs](slides/02_structured_outputs.md)** | Grammar-constrained decoding vs JSON mode, Pydantic v2 & Zod schemas, self-repair loops. | `python/src/m02_structured_outputs/` | `typescript/src/m02_structured_outputs/` |
| **03** | **[Prompt Caching & KV-Cache](slides/03_prompt_caching_and_kvcache.md)** | GPU VRAM PagedAttention, Anthropic breakpoints, OpenAI prefix caching, Gemini Context Caching, 6 cache-breaking traps. | `python/src/m03_prompt_caching/` | `typescript/src/m03_prompt_caching/` |
| **04** | **[Asynchronous Batch Inference](slides/04_batch_inference.md)** | 50% discount economics, JSONL batch pipelines, polling state machines, row-level dead letters. | `python/src/m04_batch_processing/` | `typescript/src/m04_batch_processing/` |
| **05** | **[Resilience, Rate Limits & Errors](slides/05_error_handling_resilience.md)** | 400/429/500/529 HTTP taxonomy, Exponential Backoff with Full Jitter, Circuit Breakers, Multi-provider Fallback Cascade. | `python/src/m05_resilience/` | `typescript/src/m05_resilience/` |
| **06** | **[Gateways & Observability](slides/06_gateways_and_cost_optimization.md)** | LiteLLM proxy vs OpenRouter, virtual keys, dynamic model routing, dual-telemetry (LangSmith + SIEM), and OpenTelemetry GenAI standards. | `python/src/m06_gateways/` | `typescript/src/m06_gateways/` |
| **07** | **[Frontend Agent Architectures](slides/07_frontend_agent_architectures.md)** | In-process monolith vs decoupled SSE microservices, Streamlit chat integration, TypeScript web app SPA, Server-Sent Events wire protocols, and extensible tool registries. | `python/src/langchain_suite/frontend_agent/` | `typescript/src/langchain_suite/frontend_agent/` |
| **LC** | **LangChain & LangGraph Suite** | High-level enterprise orchestration: unified chat streaming, telemetry callbacks, Pydantic v2 / Zod structured extraction, prompt caching blocks, concurrency-throttled batching, declarative fallback cascades, dynamic routers, stateful tool-calling agents with SQLite crash recovery, and OpenTelemetry GenAI Semantic Conventions bridge. | `python/src/langchain_suite/` | `typescript/src/langchain_suite/` |

---

## 🧪 Student Hands-on Engineering Labs

The **[exercises/](./exercises)** directory contains 5 production-grade engineering challenges complete with starters (`TODO` markers), reference solutions, and automated test harnesses across both Python and TypeScript:

1. **[Lab 01: Token-Bucket Rate Limiter & Jittered Retry](exercises/lab01_rate_limiter)**: Build proactive client-side rate limiters and decorrelated jitter to avoid HTTP 429 thundering herds.
2. **[Lab 02: Prompt Cache Optimization & Audit](exercises/lab02_prompt_cache_audit)**: Audit a broken prompt assembly pipeline that suffers from timestamp injection and unstable serialization to achieve $\ge 90\%$ cache hit rates.
3. **[Lab 03: Multi-Provider Fallback Cascade with Circuit Breakers](exercises/lab03_resilience_cascade)**: Implement a 3-tier cascade (Claude Sonnet $\to$ GPT-4o $\to$ Gemini Flash) with circuit breaker isolation.
4. **[Lab 04: Batch API Cost Arbitrage Pipeline](exercises/lab04_batch_pipeline)**: Build an asynchronous batch ingestion engine with line error isolation and audited 50% cost savings.
5. **[Lab 05: Fault-Tolerant State Machine & SQLite Crash Recovery](exercises/lab05_langgraph_recovery)**: Build a cyclical LangGraph state machine with tools routing, SQLite checkpointing, and process crash recovery.

### Running Laboratory Tests

```powershell
# Python Stack (uv + pytest - runs all 5 labs):
cd python
uv run pytest ../exercises/

# TypeScript Stack (Node.js 24 + tsx - runs all 5 labs):
cd typescript
npm test
```

---

## 👨‍🏫 Instructor & Facilitator Guide

See **[INSTRUCTOR_GUIDE.md](./INSTRUCTOR_GUIDE.md)** for:
- 1-Day Intensive (8h) and 2-Day Workshop (16h) delivery timetables.
- Slide-by-slide facilitator talking points, live whiteboard prompts, and common student pitfalls.
- Lab facilitation hints and grading rubrics.

---

## 🏛️ System Architecture Diagrams

- **Anthropic Interactions Lifecycle** ([MMD](diagrams/anthropic_interactions_lifecycle.mmd) | [PNG](diagrams/anthropic_interactions_lifecycle.png) | [SVG](diagrams/anthropic_interactions_lifecycle.svg)): Claude 5.5 interaction lifecycle spanning system instructions, cached document blocks, mid-conversation system injections, effort reasoning blocks, SSE deltas (`thinking_delta`, `signature_delta`, `text_delta`), strict tools, and citation extraction.
- **Frontend Agent Architectures** ([MMD](diagrams/frontend_agent_architectures.mmd) | [PNG](diagrams/frontend_agent_architectures.png) | [SVG](diagrams/frontend_agent_architectures.svg)): In-process monolithic execution vs decoupled FastAPI SSE microservice.
- **SSE Streaming Sequence & Tool Lifecycle** ([MMD](diagrams/sse_lifecycle_sequence.mmd) | [PNG](diagrams/sse_lifecycle_sequence.png) | [SVG](diagrams/sse_lifecycle_sequence.svg)): End-to-end event sequence between browser, Streamlit, FastAPI, LangGraph, tools, and LLM.
- **Dual-Telemetry & OpenTelemetry Architecture** ([MMD](diagrams/dual_telemetry_otel.mmd) | [PNG](diagrams/dual_telemetry_otel.png) | [SVG](diagrams/dual_telemetry_otel.svg)): Multiplexed telemetry pipeline: LangSmith visual tracing, in-band PII-scrubbed SIEM logs, and OTel GenAI standard spans.
- **KV-Cache vs Prompt Caching Architecture** ([MMD](diagrams/kv_cache_vs_prompt_cache.mmd) | [PNG](diagrams/kv_cache_vs_prompt_cache.png) | [SVG](diagrams/kv_cache_vs_prompt_cache.svg)): GPU memory block reuse vs cluster prefix hashing and cache-breaking factors.
- **Batch Inference Lifecycle** ([MMD](diagrams/batch_lifecycle.mmd) | [PNG](diagrams/batch_lifecycle.png) | [SVG](diagrams/batch_lifecycle.svg)): Sequence flow of asynchronous 50%-discount batch execution and polling.
- **Multi-Provider Fallback Cascade** ([MMD](diagrams/fallback_cascade.mmd) | [PNG](diagrams/fallback_cascade.png) | [SVG](diagrams/fallback_cascade.svg)): Resilient fallback flow between Claude, OpenAI, and Gemini with circuit breaker protection.
- **LLM Gateway Architecture** ([MMD](diagrams/gateway_architecture.mmd) | [PNG](diagrams/gateway_architecture.png) | [SVG](diagrams/gateway_architecture.svg)): Centralized proxy routing, virtual keys, tiered economics, and spend controls.
- **Gateway Request Lifecycle** ([MMD](diagrams/gateway_request_lifecycle.mmd)): Pre-call guardrails, semantic caching, provider routing, and post-call audit telemetry.
- **Gateway Resilience & Fallbacks** ([MMD](diagrams/gateway_resilience_fallbacks.mmd)): Circuit breaker tripping, rate-limit cascades, and zero-downtime routing.
- **Structured Outputs Mechanics** ([MMD](diagrams/structured_outputs_mechanics.mmd) | [PNG](diagrams/structured_outputs_mechanics.png) | [SVG](diagrams/structured_outputs_mechanics.svg)): Grammar state machines vs legacy prompt-based JSON.

---

## 📚 Deep-Dive Engineering Guides

1. **[API Comparison Matrix](docs/api_comparison_matrix.md)**: Exhaustive side-by-side feature comparison between OpenAI, Anthropic, and Gemini.
2. **[Prompt Caching Rules & Pitfalls](docs/prompt_caching_rules.md)**: The 6 deadly mistakes that silently invalidate prompt caches.
3. **[Error Handling & Rate Limits Cheat Sheet](docs/error_code_cheatsheet.md)**: HTTP status codes, headers, and retry strategies.
4. **[Cost Optimization Playbook](docs/cost_optimization_guide.md)**: Tactical formulas to reduce LLM bills by 60%–85%.
5. **[LLM Gateways Architecture & Engineering Guide](docs/llm_gateways_guide.md)**: Authoritative enterprise blueprints for **LiteLLM** and **OpenRouter** covering cost, performance, master key vaulting, PII guardrails, and batch APIs.
6. **[LangSmith & Enterprise Structured Logging Guide](docs/langsmith_and_structured_logging.md)**: Dual-telemetry architecture, RunTree hierarchy, PII redaction, OpenTelemetry bridge, and in-band SIEM log streams.

### 🔗 Anthropic Engineering Reference Hub
- **Messages & Wire Protocols**: [working-with-messages](https://platform.claude.com/docs/en/build-with-claude/working-with-messages)
- **SSE Streaming & Thinking Deltas**: [streaming](https://platform.claude.com/docs/en/build-with-claude/streaming)
- **Thinking Effort & Budgets**: [effort](https://platform.claude.com/docs/en/build-with-claude/effort)
- **Native Structured Outputs**: [structured-outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
- **Document Citations & Verification**: [citations](https://platform.claude.com/docs/en/build-with-claude/citations)

---

## ⚡ Quickstart

### 1. Environment Setup

Copy `.env.example` to `.env` in both `python/` and `typescript/` and add your API keys:

```bash
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=AIzaSy...
OPENROUTER_API_KEY=sk-or-...

# Optional: LangSmith Tracing
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=lsv2_pt_...
LANGCHAIN_PROJECT=telekom-agent-prod
```

### 2. Running Python Examples (`uv`)

```powershell
cd python
# Install dependencies into virtualenv managed by uv
uv sync

# Run direct SDK module examples
uv run python -m src.m01_paradigms.chat_comparison
uv run python -m src.m02_structured_outputs.openai_strict
uv run python -m src.m03_prompt_caching.cache_invalidation_demo
uv run python -m src.m05_resilience.fallback_cascade
uv run python -m src.m06_gateways.cost_calculator
uv run python -m src.m06_gateways.openrouter_integration
uv run python -m src.m06_gateways.litellm_integration

# Run LangChain & LangGraph suite examples
uv run python -m src.langchain_suite.m01_paradigms.unified_chat
uv run python -m src.langchain_suite.m02_structured.structured_output
uv run python -m src.langchain_suite.m05_resilience.fallback_cascade
uv run python -m src.langchain_suite.m06_gateways.cost_router
uv run python -m src.langchain_suite.m06_gateways.gateway_orchestrator
uv run python -m src.langchain_suite.agent_recovery.recover_demo
uv run python -m src.langchain_suite.agent_recovery.dual_telemetry_demo

# Run Tests
uv run pytest tests/test_gateways.py
uv run pytest tests/

# Run Module 07 Frontend Agent Showcase (Streamlit + FastAPI SSE microservice)
uv run python -m src.langchain_suite.frontend_agent.run_showcase --all
uv run pytest tests/test_frontend_agent.py
```

### 3. Running TypeScript Examples (`npm` / `tsx`)

```powershell
cd typescript
# Install dependencies
npm install

# Run direct SDK module examples
npm run start:m01
npm run start:m02
npm run start:m03
npm run start:m05
npm run start:m06
npm run start:m06:openrouter
npm run start:m06:litellm

# Run LangChain & LangGraph suite examples
npm run start:lc:m01
npm run start:lc:m02
npm run start:lc:m05
npm run start:lc:m06
npm run start:lc:m06:gateway
npm run start:lc:agent
npm run start:lc:telemetry

# Run Tests
npm run test:gateways
npm test

# Run Module 07 Frontend Agent Showcase (Express SPA + Standalone SSE Agent microservice)
npm run start:frontend:all
npm run test:frontend-agent
```

### 4. Compiling & Presenting Slides

All 7 presentation decks can be compiled into self-contained HTML presentations using Marp:

```powershell
# Using the automated build script:
.\scripts\build_slides.ps1

# Or on macOS/Linux:
./scripts/build_slides.sh
```

Pre-compiled HTML slides are available in `dist/slides/`. Open any `.html` file in your browser to present directly!
