# Python Examples: Advanced GenAI API Integration

This directory contains production-ready Python examples implemented with modern Python 3.12 and managed via **[`uv`](https://docs.astral.sh/uv/)**.

---

## 🛠️ Setup

1. **Install uv** (if not already installed):
   ```bash
   # Windows PowerShell
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```

2. **Sync the project virtual environment**:
   ```bash
   uv sync
   ```

3. **Configure Environment Variables**:
   ```bash
   cp .env.example .env
   # Edit .env with your provider API keys
   ```

---

## 📂 Module Map & CLI Execution

### Module 1: API Paradigms & Wire Protocols
- **Client Factory**: Initializes OpenAI, Anthropic, and Gemini SDKs with verification.
- **Chat Comparison**: Run completion across all 3 providers and inspect normalized token usage.
  ```bash
  uv run python -m src.m01_paradigms.chat_comparison
  ```
- **Streaming Comparison**: Stream chunks via SSE and extract usage chunks cleanly.
  ```bash
  uv run python -m src.m01_paradigms.streaming_comparison
  ```
- **Tool Calling**: Cross-provider function calling comparison.
  ```bash
  uv run python -m src.m01_paradigms.tool_calling
  ```

### Module 2: The Response API & Structured Outputs
- **OpenAI Strict JSON Schema**: Grammar-constrained decoding using Pydantic v2.
  ```bash
  uv run python -m src.m02_structured_outputs.openai_strict
  ```
- **Anthropic Tool-Choice Coercion**: Schema enforcement pattern.
  ```bash
  uv run python -m src.m02_structured_outputs.anthropic_structured
  ```
- **Google Gemini Response Schema**: Direct Pydantic output.
  ```bash
  uv run python -m src.m02_structured_outputs.gemini_structured
  ```
- **Self-Healing JSON Parser**: Automatically repairs truncated or malformed responses.
  ```bash
  uv run python -m src.m02_structured_outputs.self_repair
  ```

### Module 3: Prompt Caching & The KV-Cache
- **Cache Invalidation Benchmark**: Demonstrates how dynamic timestamps break cache hits vs static prefixes.
  ```bash
  uv run python -m src.m03_prompt_caching.cache_invalidation_demo
  ```
- **Anthropic Breakpoints**: 4-breakpoint rolling cache implementation.
  ```bash
  uv run python -m src.m03_prompt_caching.anthropic_cache
  ```
- **OpenAI Automatic Caching**: Prefix matching verification.
  ```bash
  uv run python -m src.m03_prompt_caching.openai_cache
  ```

### Module 4: Asynchronous Batch Inference
- **OpenAI Batch Pipeline**: File upload, batch creation, status polling loop.
  ```bash
  uv run python -m src.m04_batch_processing.openai_batch
  ```
- **Anthropic Message Batches**: Creation and status tracking.
  ```bash
  uv run python -m src.m04_batch_processing.anthropic_batch
  ```
- **Resilient Batch Orchestrator**: State machine with dead-letter queue.
  ```bash
  uv run python -m src.m04_batch_processing.batch_orchestrator
  ```

### Module 5: Resilience, Errors & Rate Limits
- **Error Taxonomy**: Translates HTTP 400, 429, 500, 529 to structured exceptions.
  ```bash
  uv run python -m src.m05_resilience.error_taxonomy
  ```
- **Retry with Full Jitter**: Decorator avoiding thundering herd problems.
  ```bash
  uv run python -m src.m05_resilience.retry_with_jitter
  ```
- **Circuit Breaker**: Closed -> Open -> Half-Open state machine.
  ```bash
  uv run python -m src.m05_resilience.circuit_breaker
  ```
- **Multi-Provider Fallback Cascade**: Claude -> GPT-4o -> Gemini failover.
  ```bash
  uv run python -m src.m05_resilience.fallback_cascade
  ```

### Module 6: Gateways & Cost Minimization
- **LiteLLM Unified Interface & Budgets**:
  ```bash
  uv run python -m src.m06_gateways.litellm_integration
  ```
- **OpenRouter Dynamic Routing**:
  ```bash
  uv run python -m src.m06_gateways.openrouter_integration
  ```
- **Interactive Cost Calculator**:
  ```bash
  uv run python -m src.m06_gateways.cost_calculator
  ```

### Streamlit & LangChain Agent UI Integrations
Demonstrates two enterprise architectural patterns connecting Streamlit chat UIs with LangChain/LangGraph tool-calling agents:
- **Pattern A (In-Process Monolith)**: Agent runs directly in the Streamlit worker process.
- **Pattern B (Decoupled Microservice)**: FastAPI executes the agent and streams lifecycle events over **Server-Sent Events (SSE)**.
- **Tools (V1)**: `get_current_time` (timezone-aware) and `get_random_quote` (categorized quotes) with extensible `ToolRegistry`.

```bash
# Run both FastAPI backend and Streamlit frontend:
uv run python -m src.langchain_suite.frontend_agent.run_showcase --all

# Or run frontend only (defaults to Pattern A):
uv run python -m src.langchain_suite.frontend_agent.run_showcase --frontend
```


