# Deep Dive: Prompt Caching & The KV-Cache Invalidation Rules

## 1. What is the KV-Cache Under the Hood?

During Transformer inference, generation operates in two distinct phases:

1. **Prefill (Prompt Evaluation)**:
   - Takes all $N$ tokens of the prompt simultaneously.
   - Computes Key ($K$) and Value ($V$) projection tensors across all attention heads and layers.
   - Computation scale: $O(N^2)$ due to full bidirectional/causal attention matrix multiplication.
   - Memory scale: Stored in high-bandwidth GPU memory (HBM/VRAM) using **PagedAttention** (virtual memory paging for LLM tensors).

2. **Decoding (Autoregressive Generation)**:
   - Produces 1 new token at a time.
   - Reuses the existing $K$ and $V$ tensors from GPU memory without re-evaluating preceding tokens.
   - Computational cost per step: $O(N)$ instead of $O(N^2)$.

**Prompt Caching** at the API provider level extends this concept beyond a single request:  
When two requests share an identical prefix of tokens, the provider can load the precomputed $K, V$ states from high-speed memory or NVMe clusters rather than running an expensive matrix multiplication prefill again.

---

## 2. Vendor Implementations Compared

| Dimension | Anthropic Claude (3.5 / 3.7 / 5.x) | OpenAI Classic (GPT-4o / o-series) | OpenAI Modern (GPT-5.6+ / GPT-6 / GPT-6.1 Sol) | Google Gemini (Enterprise Agent Platform) |
| :--- | :--- | :--- | :--- | :--- |
| **Strategy** | **Explicit Breakpoints & Top-Level Auto** | **Automatic Prefix Matching** | **Dual Mode**: Explicit Breakpoints & Implicit | **Dual Mode**: Implicit (Default) & Explicit (API) |
| **Models Supported** | Claude Opus 5.5 / Sonnet 5.5 / Haiku 5.5, Claude Opus 5, Claude Fable 5.1 / Mythos 5.1 *(legacy: Claude 3.5 / 3.7)* | GPT-4o, GPT-4o-mini, o1, o1-mini, o3-mini | GPT-5.6, GPT-6, GPT-6.1 Sol (Responses API) | Gemini 2.5 Flash / Pro, Gemini 2.0, Gemini 3 family |
| **Activation Syntax** | Block-level `cache_control: {"type": "ephemeral"}` or Top-level request `cache_control` | Automatic (no configuration or tags) | `prompt_cache_breakpoint: {"mode": "explicit"}` or `prompt_cache_options.mode: "implicit"` | Automatic prefix (Implicit) / `CachedContent` resource (Explicit) |
| **Minimum Tokens** | **1,024** (Opus 5.5 / Sonnet 5.5 / Opus 5 / 5.x) <br> **2,048** (Haiku 5.5) | **1,024 tokens** | **1,024 tokens** | **Gemini 2**: 2,048 tokens <br> **Gemini 3**: 4,096 tokens (6,144 for 3.7/3.8 Flash implicit preview) |
| **Matching Granularity** | Exact block up to breakpoint; prefix matching searches back at most **20 blocks** | **128-token increments** | Exact block (Explicit, suffix billed at standard rate) or message end | Exact prefix sequence |
| **Breakpoint Limits** | Up to **4 breakpoints** per request (top-level auto-cache consumes 1 slot) | Unlimited prefix matching | Up to **4 explicit write slots** | Exact prefix (Implicit) or Named resource (Explicit) |
| **Read Discount** | **90% to 95% off** (0.10x to 0.05x on Opus/Sonnet 5.5; **97.5% off / 0.025x** on Mythos 5.1) | **50% off base input** (0.50x rate) | **90% off base input** (0.10x rate; **95% off / 0.05x** on GPT-6.1 Sol) | **90% off for Gemini 2.5+** (75% on Gemini 2.0) |
| **Write / Storage Cost** | **5m TTL**: 125% base price (1.25x) <br> **1h TTL**: 200% base price (2.0x) | **100% standard input price** (0% surcharge) | **125% of input price** (25% write surcharge on cached content) | **Implicit**: $0.00 storage fee <br> **Explicit**: Hourly TTL storage (default 60m) |
| **Eviction Policy / TTL** | **5-minute rolling TTL** (default) or **1-hour extended TTL** (`"ttl": "1h"`) | Dynamic cluster LRU (5-60 mins) or `"24h"` retention | **30-minute rolling TTL** minimum (`prompt_cache_options.ttl: "30m"`) | **Implicit**: Dynamic LRU <br> **Explicit**: Configurable TTL (1 min to indefinite) |
| **Routing / Isolation** | Default tenant routing | `prompt_cache_key` cluster affinity (~15 req/min) | `prompt_cache_key` tenant accounting & anti-probing isolation | GCP Project Isolation + VPC Service Controls |
| **Telemetry Field** | `usage.cache_read_input_tokens`<br>`usage.cache_creation_input_tokens` | `usage.prompt_tokens_details.cached_tokens` | `usage.input_tokens_details.cached_tokens`<br>`usage.input_tokens_details.cache_write_tokens` | `usage_metadata.cached_content_token_count` |
| **Diagnostics** | Opt-in `diagnostics: {"previous_message_id": ...}` $\rightarrow$ `cache_miss_reason`, `cache_missed_input_tokens` | N/A | `prompt_cache_options.comparison_response_id` & `prompt_cache_diagnostics` | Telemetry & Audit Logs |


---

## 3. The 9 Deadly Sins: What Silently Breaks the Cache?

Because caching is based on **exact prefix hashing**, even a single modified byte at the beginning of the prompt invalidates **everything that follows it**.

### ❌ Invalidation 1: Dynamic Timestamps in System Prompts
```python
# BROKEN: Every request gets a fresh timestamp at token index 15.
# Result: 0% cache hit rate!
system_prompt = f"You are a helpful assistant. Current time: {datetime.now().isoformat()}..."

# FIXED: Move static policies to the system prompt prefix; inject variable data at the END of the conversation.
system_prompt = "You are a helpful assistant. Follow strict compliance rules..."
user_message = f"[Current context: {datetime.now().isoformat()}]\nUser query: {query}"
```

### ❌ Invalidation 2: Non-Deterministic Tool Array Ordering
```python
# BROKEN: Set or unordered dictionary iteration in Python yields randomized JSON tool schemas.
tools = list({t["name"]: t for t in tools}.values()) # Order may fluctuate!

# FIXED: Always sort tool definitions deterministically by name before sending.
tools = sorted(raw_tools, key=lambda t: t["function"]["name"])
```

### ❌ Invalidation 3: User/Session Identifiers Injected Upstream
```python
# BROKEN: System prompt contains unique session ID. Every user experiences a cold cache miss.
system_prompt = f"User session: {session_id}. Knowledge base:\n{huge_document_10k_tokens}"

# FIXED: Place invariant documents FIRST.
# [Static Document 10k tokens] -> [Break Point] -> [Session Info] -> [User Question]
```

### ❌ Invalidation 4: Inconsistent Whitespace, Newlines, or Indentation
- Changing `\r\n` to `\n` changes token IDs.
- Changing `json.dumps(obj)` to `json.dumps(obj, indent=2)` completely alters token sequences.
- Serializing JSON with variable key sorting: always use `json.dumps(obj, sort_keys=True)`.

### ❌ Invalidation 5: Falling Below the Minimum Token Threshold & Boundary Mismatch
- **Anthropic**: Requires $\ge 1,024$ tokens on Claude 3.7 Sonnet / Claude 3.5 Sonnet / Opus, and $\ge 2,048$ tokens on Claude Haiku.
- **OpenAI**: Requires $\ge 1,024$ tokens for automatic caching. Tokens beyond 1,024 are cached in **128-token increment blocks**. A prompt with 1,150 tokens will cache only the first 1,024 or 1,152 (nearest 128 boundary). Aligning large static sections to multiples of 128 tokens maximizes hit efficiency.
- **Google Gemini (Enterprise Agent Platform)**:
  - **Gemini 2 family** (e.g., Gemini 2.5 Flash, Gemini 2.5 Pro): $\ge 2,048$ tokens for implicit and explicit caching.
  - **Gemini 3 family**: $\ge 4,096$ tokens for explicit caching; $\ge 6,144$ tokens for implicit caching on Gemini 3.0 Flash Preview, 3.1 Pro Preview, 3.7 Flash, and 3.8 Flash.

### ❌ Invalidation 6: Anthropic 4-Breakpoint Exhaustion & Placement Defects
- **Breakpoint Limit**: Anthropic permits a maximum of **4** `cache_control` breakpoints per request.
- **Top-Level Request Caching**: Passing `cache_control: {"type": "ephemeral"}` at the Messages request root automatically caches the final cacheable block and consumes **1 of your 4 breakpoint slots**, leaving at most 3 explicit block-level breakpoints.
- Exceeding 4 cumulative `cache_control` tags returns an HTTP `400 Bad Request`.
- **20-Block Lookback Window**: Prefix matching searches back at most **20 blocks** (consecutive `tool_use` or `tool_result` blocks count as a single position). In rapid agentic loops with $\ge 20$ blocks between turns, omit or place intermediate explicit breakpoints to maintain continuity.
- **Tool Caching**: You can attach `cache_control` to tool definitions (`tools: [{ ..., cache_control: {"type": "ephemeral"} }]`). Placing it on the last tool caches the system prompt and all tools in a single unified prefix.
- Placing `cache_control` on volatile user turns will repeatedly incur the write surcharge (1.25x for 5m, 2.0x for 1h) without yielding cache hits!

### ❌ Invalidation 7: The Message Extension Pitfall (Boundary Shift)
In multi-turn chat applications, developers often append additional text to the previous message rather than appending a brand-new turn:
```python
# BROKEN: Modifying or appending text to an existing turn moves its ending boundary!
# Turn 1:
messages = [{"role": "user", "content": "Analyze network topology."}]
# Turn 2:
messages = [{"role": "user", "content": "Analyze network topology. Focus specifically on BGP peering routes."}]
```
- **Why it breaks**: In implicit caching mode, candidate breakpoints are placed at the **end** of eligible message turns. When you expand Turn 1's content, the boundary shifts to the end of the new string. The precomputed KV-cache for Turn 1 cannot be matched because there is no boundary marker at the original stopping point.
- **Remediation**: Always append new turns as discrete, separate message objects in the array (`[{"role": "user", ...}, {"role": "assistant", ...}, {"role": "user", ...}]`). If modifying an existing message is unavoidable, place an explicit breakpoint (`prompt_cache_breakpoint: {"mode": "explicit"}`) at the boundary of the original content.

### ❌ Invalidation 8: Cache Mode Switching Across Turns (Implicit ↔ Explicit)
In OpenAI's modern Responses API:
- If Turn 1 is submitted with `prompt_cache_options: {"mode": "implicit"}` (or left to default implicit caching), the model writes cache entries at implicit message boundaries.
- If Turn 2 switches to `prompt_cache_options: {"mode": "explicit"}` without matching explicit breakpoints, the lookup evaluation scans only explicit breakpoints and misses the implicit cache written during Turn 1!
- **Remediation**: Keep `prompt_cache_options.mode` consistent across the entire conversation lifecycle.

### ❌ Invalidation 9: TPM Rate Limit Inelasticity on Cached Tokens
- While cached tokens enjoy substantial financial discounts (up to 90%–97.5% off), providers (both OpenAI and Anthropic) still count cached tokens **100% against your Tokens-Per-Minute (TPM) quota**.
- **The Risk**: An application firing high-frequency requests with massive 100k-token cached contexts will remain cheap financially, but can trigger HTTP `429 Too Many Requests (Rate limit exceeded: TPM)` if aggregate traffic exceeds the organization's TPM tier.
- **Remediation**: Size TPM quotas according to the *full uncompressed token volume*, regardless of expected cache hit ratios.

---

## 4. Architectural Best Practice: Prefix Layering

Structure all multi-turn and agent prompts in the following strict order:

```
┌────────────────────────────────────────────────────────┐
│ 1. Static System Instructions (Rules, Personas)        │  <-- CACHED (Breakpoint 1)
├────────────────────────────────────────────────────────┤
│ 2. Tool / Function Calling Schemas (Deterministically Sorted)│  <-- CACHED (Breakpoint 2)
├────────────────────────────────────────────────────────┤
│ 3. Static Knowledge Base / Uploaded Documents (10k+ tok)│  <-- CACHED (Breakpoint 3)
├────────────────────────────────────────────────────────┤
│ 4. Historical Conversation Messages (Turns 1..N-2)     │  <-- CACHED (Breakpoint 4 - Rolling)
├────────────────────────────────────────────────────────┤
│ 5. Latest User Query & Dynamic Context (Timestamps, GPS)│  <-- UNCACHED (Fresh Tokens)
└────────────────────────────────────────────────────────┘
```

---

## 5. Agentic Security & Context Cache Isolation (Google Gemini Enterprise)

When designing multi-agent or multi-tenant agent platforms:

1. **GCP Project Isolation**:
   - Google Cloud isolates context caches strictly by GCP project number. Cached contents are never shared across projects.
2. **Execution Context Scoping (Zero Cross-User Leakage)**:
   - For agentic pipelines with shared gateways, ensure cache boundaries align strictly with user authorization boundaries. Never cache user credentials, authentication tokens, or private conversational turns in shared prefixes.
3. **VPC Service Controls (VPC-SC)**:
   - Context caching supports VPC Service Controls, ensuring cached tokens and prompt prefixes cannot be exfiltrated outside the secure perimeter.
4. **Cloud Storage Immutability During Cache Lifetime**:
   - When building explicit caches from Cloud Storage buckets, do not mutate bucket objects while active caches reference them; updates to underlying GCS objects cause cached contents to become unusable.

---

## 6. Economic Break-Even & Financial ROI Analysis

Prompt caching economics differ substantially between vendors and model generations:

### Anthropic Claude (5m TTL vs 1h TTL & Modern Model Discounts)
- **Standard 5-Minute Rolling TTL (Claude 3.5 / 3.7)**:
  - **Call 1 (Cache Write)**: $1.25 \times P_{\text{input}}$ (a 25% write surcharge).
  - **Call 2 (Cache Read)**: $0.10 \times P_{\text{input}}$ (a 90% read discount).
  - **Two-call total**: $1.25 + 0.10 = 1.35 \times P_{\text{input}}$ vs. $2.0 \times P_{\text{input}}$ uncached (**32.5% net savings** at Turn 2).
  - **Ten-call total**: $1.25 + (9 \times 0.10) = 2.15 \times P_{\text{input}}$ vs. $10.0 \times P_{\text{input}}$ uncached (**78.5% net savings** at Turn 10).
- **Extended 1-Hour TTL (`"ttl": "1h"`)**:
  - **Call 1 (Cache Write)**: $2.00 \times P_{\text{input}}$ (a 100% write premium).
  - **Call 2 (Cache Read)**: $0.10 \times P_{\text{input}}$ (90% discount).
  - **Two-call total**: $2.00 + 0.10 = 2.10 \times P_{\text{input}}$ vs. $2.0 \times P_{\text{input}}$ uncached (slight investment).
  - **Three-call total**: $2.00 + 0.20 = 2.20 \times P_{\text{input}}$ vs. $3.0 \times P_{\text{input}}$ uncached (**26.7% net savings** at Turn 3).
  - **Ten-call total**: $2.00 + (9 \times 0.10) = 2.90 \times P_{\text{input}}$ vs. $10.0 \times P_{\text{input}}$ uncached (**71.0% net savings**).
  - **ROI Justification**: For workloads with inter-turn gaps of 5 to 60 minutes, the 5-minute cache will have expired (causing multiple 1.25x cold re-writes), whereas 1h TTL pays the 2.0x fee once and yields 0.10x reads across the entire hour.
- **Modern Model Tier Discounts**:
  - **Claude Opus 5.5 / Sonnet 5.5**: **0.05x read rate (95% discount)** $\rightarrow$ Ten-call total: $1.25 + (9 \times 0.05) = 1.70 \times P_{\text{input}}$ (**83.0% net savings**).
  - **Claude Fable 5.1 / Mythos 5.1**: **0.025x read rate (97.5% discount)** $\rightarrow$ Ten-call total: $1.25 + (9 \times 0.025) = 1.475 \times P_{\text{input}}$ (**85.25% net savings**).

### OpenAI Classic (GPT-4o / o-series: 1.00x Write vs 0.50x Read)
- **Call 1 (Cache Write)**: $1.00 \times P_{\text{input}}$ (Zero write surcharge).
- **Call 2 (Cache Read)**: $0.50 \times P_{\text{input}}$ (50% discount).
- **Rule**: Zero write penalty means **immediate risk-free savings** on Call 2 onwards.

### OpenAI Modern (GPT-5.6+ / GPT-6 / GPT-6.1 Sol: 1.25x Write vs 0.10x / 0.05x Read)
- **Call 1 (Cache Write)**: $1.25 \times P_{\text{input}}$ (25% write surcharge).
- **Call 2 (Cache Read)**: $0.10 \times P_{\text{input}}$ (90% discount on GPT-6; **0.05x / 95% discount** on GPT-6.1 Sol).
- **Two-call total**: $1.25 + 0.10 = 1.35 \times P_{\text{input}}$ vs. $2.0 \times P_{\text{input}}$ uncached (**32.5% net savings** at Turn 2).
- **Ten-call total (GPT-6.1 Sol)**: $1.25 + (9 \times 0.05) = 1.70 \times P_{\text{input}}$ vs. $10.0 \times P_{\text{input}}$ uncached (**83.0% net savings** at Turn 10).
- **Rule**: Breakeven occurs on Call 2, with higher long-tail margins than classic prefix matching.

### Google Gemini Implicit Caching (1.00x Write vs 0.10x Read, $0.00 Storage)
- **Call 1 (Cache Write)**: $1.00 \times P_{\text{input}}$ (Zero write surcharge).
- **Call 2 (Cache Read)**: $0.10 \times P_{\text{input}}$ (90% discount on Gemini 2.5+).
- **Rule**: Highest immediate ROI in the industry—zero storage fee and 90% read discount from Call 2 onward.

---

## 7. OpenAI Modern Prompt Caching Architecture (Responses API)

With GPT-5.6+, GPT-6, and GPT-6.1 Sol, OpenAI introduced a dual-mode caching architecture built directly into the Responses API, designed for predictable enterprise latency, deterministic cost management, and multi-tenant isolation.

### 1. Dual-Mode Operation: Explicit vs. Implicit

OpenAI provides two distinct modes for caching prefixes, controlled via `prompt_cache_options.mode`:

#### A. Explicit Mode (`prompt_cache_options.mode: "explicit"`)
- Developers explicitly designate cache boundaries on specific input blocks using:
  ```json
  "prompt_cache_breakpoint": {"mode": "explicit"}
  ```
- **Capacity**: Supports up to **4 explicit write slots** per API request.
- **Suffix Cost Protection**:
  - In explicit mode, the API only writes cache entries up to the explicit breakpoints you have tagged.
  - Any input content placed *after* the final explicit breakpoint (e.g., dynamic user queries, volatile turn variables, session metadata) is treated as ephemeral suffix content.
  - **Billing Impact**: Suffix content is billed at the standard 1.00x base input rate, completely exempt from the 1.25x write surcharge! This prevents developers from accidentally paying a 25% write penalty on tokens that will never be reused in subsequent requests.

#### B. Implicit Mode (`prompt_cache_options.mode: "implicit"`)
- Operates automatically without requiring developers to manually annotate breakpoints.
- The API identifies eligible message turn boundaries and writes cache entries automatically.
- **Eligible Implicit Boundaries**:
  1. The end of the **latest user message**.
  2. The end of the **last tool response** in a contiguous group of tool messages.
  3. The end of the **last developer message** in an initial sequence of developer messages.

---

### 2. Lookup Boundaries Evaluation Algorithm

When a request arrives, OpenAI's inference engine evaluates candidate cache boundaries using a deterministic backward-scanning algorithm:

1. **Direction of Evaluation**: The engine scans candidate boundaries **backwards from longest to shortest prefix** to maximize the number of reused cached tokens.
2. **Explicit-Only Mode Scan Candidates**:
   - Tests the **first 2** explicit breakpoints in the request (typically system prompts and tool schemas).
   - Tests the **latest 50** explicit breakpoints in the request (active multi-turn conversational history).
3. **Implicit Mode Scan Candidates**:
   - Tests the **first 2** explicit breakpoints.
   - Tests the **latest 50** explicit breakpoints.
   - Tests the **latest implicit breakpoint**.
   - Tests up to **20 earlier eligible message endings**.

If a boundary match is verified against local memory, the engine reuses the precomputed $K, V$ tensors and executes prefill only for the remaining uncached suffix tokens.

---

### 3. Physical Machine Affinity, Overflow Routing & Multi-Tenant Security

Understanding the physical topology of prompt caching is critical for architecting high-throughput production systems:

#### A. The Physical Reality of KV Caches
- Unlike metadata stored in distributed databases, KV-cache tensors reside in the **high-bandwidth GPU VRAM and host RAM of individual physical machines** within an inference cluster.
- A cache hit requires that the incoming request lands on a physical worker machine that currently holds those exact KV tensors in its local memory.

#### B. The 15 RPM Traffic Overflow Threshold
- If requests sharing a specific prompt prefix or cache key arrive at a moderate rate, they are directed to the same physical machine, yielding 100% cache hits.
- **Traffic Spikes (> 15 RPM)**: When throughput exceeds approximately **15 requests per minute** for the same prefix, OpenAI's load balancer automatically routes overflow requests across multiple physical worker machines to prevent GPU resource contention.
- **Engineering Consequence**: The first request sent to each new physical node will incur a cold prefill (and a 1.25x cache write), even though an identical prompt prefix is already cached on the primary node. Once secondary nodes are warmed, the hit rate stabilizes across the distributed pool.

#### C. Evolution & Strategic Role of `prompt_cache_key`
- **Legacy / Earlier Models (GPT-4o, GPT-5.5)**:
  - `prompt_cache_key` acted as an explicit routing directive, guiding load balancers to route matching requests to the same physical hardware node.
- **Modern Models (GPT-5.6+, GPT-6, GPT-6.1 Sol)**:
  - Global cluster routing handles physical hardware affinity automatically.
  - In modern models, `prompt_cache_key` serves two critical enterprise functions:
    1. **Tenant Accounting & Quota Partitioning**: Segregates usage metrics, diagnostic telemetry, and billing records across different customers, departments, or application modules.
    2. **Cache-Hit Probing Defense**: Prevents side-channel timing attacks. In a shared multi-tenant cluster, an attacker could submit candidate text and measure Time-To-First-Token (TTFT) to deduce whether another enterprise recently processed that exact confidential document. Setting a unique `prompt_cache_key` cryptographically isolates lookup boundaries, guaranteeing that tenant A's requests can never hit or probe tenant B's cached KV tensors.

---

### 4. Cache Prewarming Protocol (`prewarm: true`)

For mission-critical, low-latency applications (e.g., real-time customer care, trading desks, voice agents), end users cannot wait for cold-start prefill on massive 20,000+ token prompts.

OpenAI provides native cache prewarming via `prompt_cache_options.prewarm: true`:
- The API processes and caches the prompt up to the designated breakpoint.
- **Zero Output Generation**: The request completes without generating any output tokens.
- **Zero TTFT Cold Start**: When end users subsequently submit queries against the prewarmed prefix, they immediately experience warm cache latency (up to 85% lower TTFT).

#### Prewarming Implementation Pattern
```python
from openai import OpenAI

client = OpenAI()

# Prewarm a massive enterprise runbook during application startup or deployment
prewarm_response = client.responses.create(
    model="gpt-6",
    input=[
        {
            "role": "system",
            "content": enterprise_system_prompt_and_kb,  # 25,000 tokens
            "prompt_cache_breakpoint": {"mode": "explicit"}
        }
    ],
    prompt_cache_options={
        "mode": "explicit",
        "prewarm": True,
        "prompt_cache_key": "tenant-telekom-core",
        "ttl": "30m"
    }
)

print("Prewarm status:", prewarm_response.status)
# Zero completion tokens generated; KV-cache is hot in GPU memory!
```

---

### 5. Mid-Conversation Configuration Updates

In complex agent workflows, you frequently need to adjust runtime hyperparameters (e.g., increasing reasoning effort when encountering an error, or tuning sampling temperature) mid-session.

Traditionally, altering parameters in the request payload risked modifying header metadata or prefix hashing. OpenAI resolves this with the typed `configuration_update` input item:

```python
# Append a configuration update as a discrete input item in the conversation
response = client.responses.create(
    model="gpt-6",
    input=[
        # Previous conversation turns remain identical and cached
        {"role": "user", "content": "Analyze the customer complaint."},
        {"role": "assistant", "content": "Initial diagnosis complete..."},
        # Dynamically escalate reasoning effort without breaking the cached prefix:
        {
            "type": "configuration_update",
            "reasoning": {
                "effort": "high"
            }
        },
        {"role": "user", "content": "Now formulate the regulatory compliance response."}
    ],
    prompt_cache_options={
        "prompt_cache_key": "tenant-telekom-core"
    }
)
```
The `configuration_update` modifies model reasoning behavior for subsequent turns while keeping all preceding cached conversation history intact.

---

## 8. OpenAI Prompt Cache Diagnostics Taxonomy

When debugging cache performance, OpenAI provides programmatic diagnostic reasoning via `prompt_cache_options.comparison_response_id`.

### Diagnostic Request Pattern
```python
# Pass the ID of a previous successful response to compare against
response = client.responses.create(
    model="gpt-6",
    input=messages,
    prompt_cache_options={
        "comparison_response_id": "resp_01j8m4k829e92a83"
    }
)

# Inspect diagnostic output
diagnostics = response.prompt_cache_diagnostics
# {
#   "type": "cache_miss",
#   "reason": "tools_changed",
#   "comparison_reusable_tokens": 1024,
#   "cache_missed_tokens": 256
# }
```

### Diagnostic Reasons Taxonomy

| Diagnostic Type | Reason Code | Root Cause | Engineering Remediation |
| :--- | :--- | :--- | :--- |
| `cache_hit` | `None` / `N/A` | Complete shared prefix matched and reused from KV-cache. | Monitor `usage.input_tokens_details.cached_tokens`. |
| `cache_miss` | `tools_changed` | Tool definitions added, removed, reordered, or schema properties mutated. | Sort tool definitions deterministically by name; keep schemas stable; use `tool_choice="none"` or `allowed_tools` rather than omitting tools. |
| `cache_miss` | `model_changed` | Dynamic model router, fallback handler, or canary deployment routed request to a different model version. | Pin exact model version strings across cache-sharing pipelines. |
| `cache_miss` | `prompt_cache_key_changed` | Tenant, partition, or workflow key differed between requests. | Keep `prompt_cache_key` consistent per tenant session; never include timestamps or ephemeral UUIDs in the key. |
| `cache_miss` | `input_changed` | Volatile token (timestamp, user ID, dynamic header) injected before or inside cached prefix. | Move all volatile data to the user message turn or suffix; keep the prefix byte-identical. |
| `cache_miss` | `reasoning_effort_changed` | Top-level `reasoning.effort` setting modified between turns. | Use a `configuration_update` input item mid-conversation to adjust reasoning effort without prefix eviction. |
| `cache_miss` | `text_format_changed` | Output schema or Structured Output format modified. | Keep `text.format` and JSON output schemas identical across consecutive requests. |
| `cache_miss` | `context_compacted` | Conversation history compaction or pruning altered earlier turns. | Ensure shared system policies precede the compacted conversation summary. |
| `cache_miss` | `service_tier_changed` | Switched between scale-tier and default priority routing. | Align `service_tier` across cache-sharing clients. |
| `cache_miss` | `verbosity_changed` | Model verbosity or tone directives mutated in prefix. | Standardize tone directives in the static prefix. |
| `comparison_response_not_found` | `N/A` | Provided `comparison_response_id` was invalid or expired. | Verify response ID is retained within the diagnostic lookup window. |
| `unavailable` | `N/A` | Diagnostic telemetry temporarily unavailable. | Retry with telemetry backoff. |

---

## 9. Prompt Cache Monitoring & The Minimum Cacheable Length Cost Trap

### Monitoring Metrics & Formulas

To accurately monitor prompt cache performance in production telemetry dashboards (Datadog, Prometheus, Grafana), track:

1. **Token Cache Hit Rate ($H_T$)**:
   $$H_T = \frac{\text{cached\_tokens}}{\text{input\_tokens}} \times 100\%$$
   - A healthy agentic production pipeline achieves $H_T \ge 80\%$.
   - If $H_T < 50\%$, run prompt cache diagnostics to identify the invalidation reason.

2. **Weighted Input Token Cost ($C_{\text{input}}$)**:
   $$C_{\text{input}} = \frac{\left( T_{\text{ordinary}} + T_{\text{cached}} \cdot r + T_{\text{write}} \cdot w \right) \cdot P_{\text{million}}}{1{,}000{,}000}$$
   Where:
   - $T_{\text{ordinary}} = T_{\text{input}} - T_{\text{cached}} - T_{\text{write}}$
   - $r = 0.10$ (Anthropic, Gemini 2.5+, OpenAI GPT-6) or $0.50$ (OpenAI GPT-4o)
   - $w = 1.25$ (Anthropic, OpenAI GPT-6) or $1.00$ (OpenAI GPT-4o, Gemini)

### The Minimum Cacheable Length Cost Trap ($L_{\text{break-even}}$ Formula)

A common engineering anti-pattern is **force-padding** prompts that fall below a provider's minimum cache threshold ($M = 1,024$ or $M = 2,048$) with dummy text or bloated instructions in order to trigger the cache.

When a provider charges a write surcharge ($w = 1.25$) and gives a read discount ($r = 0.10$), padding a short prompt of length $L < M$ up to $M$ creates an economic dilemma:

- **Unpadded (Uncached) Cost for $N$ calls**:
  $$C_{\text{unpadded}} = N \cdot L$$
- **Padded (Cached) Cost for $N$ calls**:
  $$C_{\text{padded}} = w \cdot M + (N - 1) \cdot r \cdot M = M \left( w + (N - 1)r \right)$$

For padding to be financially advantageous, we must satisfy $C_{\text{padded}} \le C_{\text{unpadded}}$:
$$M \left( w + (N - 1)r \right) \le N \cdot L$$
$$M \left( N \cdot r + (w - r) \right) \le N \cdot L$$
$$L \ge M \left( r + \frac{w - r}{N} \right)$$

This defines the **Break-Even Prompt Length**:
$$L_{\mathrm{break\text{-}even}} = M \left( r + \frac{w - r}{N} \right)$$

#### Economic Sensitivity Table ($M = 1,024$, $w = 1.25$, $r = 0.10$)

| Expected Reuses ($N$) | $\frac{w - r}{N}$ | $r + \frac{w - r}{N}$ | $L_{\mathrm{break\text{-}even}}$ (Tokens) | Decision Rule |
| :---: | :---: | :---: | :---: | :--- |
| **2 requests** | 0.575 | 0.675 | **691 tokens** | If $L < 691$, DO NOT pad; padding loses money. |
| **5 requests** | 0.230 | 0.330 | **338 tokens** | If $L < 338$, DO NOT pad. |
| **10 requests** | 0.115 | 0.215 | **220 tokens** | If $L < 220$, DO NOT pad. |
| **50 requests** | 0.023 | 0.123 | **126 tokens** | If $L \ge 126$, padding to 1,024 saves money. |
| **$\infty$ requests** | 0.000 | 0.100 | **102 tokens** | Theoretical lower bound ($r \cdot M$). |

> [!WARNING] The Padding Trap
> Never pad prompts shorter than 220 tokens unless you are guaranteed $\ge 10$ reuses within the cache TTL window. Below $L_{\text{break-even}}$, the 1.25x write fee and 1,024-token minimum exceed the cost of simply processing the unpadded prompt uncached!

---

## 10. Anthropic Prompt Cache Architecture, Extended TTL & Diagnostics

Anthropic's prompt caching provides granular breakpoint control, automatic top-level caching, extended 1-hour retention, and native programmatic diagnostics.

### 1. Breakpoint Placement & Top-Level Automatic Caching

Developers can position `cache_control` breakpoints at up to **4 positions** across:
1. `system` prompt blocks
2. Individual `tools` schema definitions
3. Conversational `messages` content blocks

#### Top-Level Automatic Caching
Rather than manually marking message blocks, Anthropic allows applying `cache_control` at the Messages request root:
```json
{
  "model": "claude-3-7-sonnet-20250219",
  "max_tokens": 1024,
  "cache_control": {"type": "ephemeral"},
  "system": [{"type": "text", "text": "Enterprise system prompt..."}],
  "messages": [...]
}
```
- **Behavior**: The API automatically caches up to the last cacheable block before the final uncached user turn.
- **Quota Consumption**: Root-level automatic caching consumes **1 of your 4 breakpoint slots**, leaving 3 slots for explicit block-level breakpoints on tools or system instructions.

### 2. Prefix Matching & The 20-Block Lookback Window

Anthropic evaluates cache breakpoints by looking backward through the request structure:
- Prefix matching scans backward at most **20 blocks** from any breakpoint.
- **Tool Block Grouping**: Consecutive `tool_use` or `tool_result` blocks in multi-tool agent turns count as a **single position** within this 20-block window.
- **Architectural Implication**: In deep agentic loops that generate more than 20 blocks between breakpoints, the lookback window cannot bridge across the gap. Developers must place intermediate explicit breakpoints on periodic agent turns to maintain cache chain continuity.

### 3. Extended 1-Hour TTL (`"ttl": "1h"`)

By default, Anthropic caches persist for a **5-minute rolling TTL** with a 1.25x write surcharge. For human-in-the-loop workflows, asynchronous agents, or batch pipelines, Anthropic provides an extended **1-hour TTL**:

```python
# Extended 1-hour cache breakpoint
system_block = {
    "type": "text",
    "text": large_knowledge_base,
    "cache_control": {"type": "ephemeral", "ttl": "1h"}
}
```

#### Economics: 5-Minute vs. 1-Hour TTL

| TTL Setting | Write Surcharge | Read Discount | Ideal Workload |
| :--- | :---: | :---: | :--- |
| **`5m` (Default)** | **1.25x** | **0.10x** (90% off) | Fast interactive chat sessions (< 5 min between turns). |
| **`1h` (Extended)** | **2.00x** | **0.10x** (90% off) | Asynchronous agent loops, batch jobs, human review queues (5–60 min between turns). |

If requests arrive 10 minutes apart:
- With **5m TTL**: Every request expires, incurring repeated cold writes ($1.25 \times N$).
- With **1h TTL**: Call 1 incurs $2.0x$, and all subsequent calls within the hour cost $0.10x$, yielding huge net savings.

> [!IMPORTANT] Monotonic TTL Ordering & Block Processing Hierarchy
> Anthropic constructs the prompt prefix in this strict architectural wire order:
> 1. `tools`
> 2. `system`
> 3. `messages`
>
> When using extended TTL (`ttl: "1h"`), Anthropic enforces that **TTL values across the prefix must be monotonically non-increasing**:
> - **A `ttl='1h'` block must NEVER come after a `ttl='5m'` block.**
> - Since `tools` are evaluated before `system`, if a tool definition has `cache_control: {"type": "ephemeral"}` (which defaults to `5m`), a subsequent `system` block cannot specify `ttl: "1h"`. Doing so triggers HTTP 400: `system.0.cache_control.ttl: a ttl='1h' cache_control block must not come after a ttl='5m' cache_control block.`
> - **Remediation**: Always assign matching `ttl: "1h"` to any preceding tool breakpoints (`{"type": "ephemeral", "ttl": "1h"}`) or reserve breakpoints exclusively for the large static system block.


### 4. Anthropic Cache Diagnostics Protocol

When cache misses occur, developers can opt into Anthropic's native diagnostics by passing the ID of the preceding assistant response via `diagnostics.previous_message_id`:

```python
response = client.messages.create(
    model="claude-3-7-sonnet-20250219",
    max_tokens=1024,
    system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
    messages=conversation_turns,
    diagnostics={"previous_message_id": last_msg_id}  # Opt-in
)

# Inspect programmatic attribution
if hasattr(response, "cache_miss_reason") and response.cache_miss_reason:
    reason_type = response.cache_miss_reason.type
    missed_tokens = getattr(response.cache_miss_reason, "cache_missed_input_tokens", None)
    print(f"Cache miss cause: {reason_type} ({missed_tokens} tokens)")
```

### 5. Anthropic Diagnostics Reason Taxonomy

| Reason Code | Root Cause | Engineering Remediation |
| :--- | :--- | :--- |
| `system_changed` | The system prompt was edited, reordered, formatted differently, or dynamic tokens (timestamps, user IDs) were injected. | Move dynamic data to the user message turn; keep system prompts byte-identical across requests. |
| `tools_changed` | Tool definitions were added, removed, reordered, or function schema parameters were altered. | Sort tools deterministically by name; avoid dynamically registering tools mid-session. |
| `messages_changed` | Prior conversation turns were mutated, trimmed, summarized, or had non-deterministic serialization. | Append new turns monotonically; place summaries behind a fresh breakpoint rather than editing past turns. |
| `model_changed` | The request was routed to a different model string (e.g., fallback from Sonnet to Haiku). | Pin the model name strictly across cache-sharing pipelines. |
| `previous_message_not_found` | The message ID supplied in `previous_message_id` was invalid, deleted, or expired past the lookup window. | Ensure message IDs are captured from the immediate preceding assistant response. |
| `unavailable` | Telemetry or cache diagnostics services were temporarily busy or unresolvable. | Rely on `usage.cache_read_input_tokens` telemetry; retry diagnostic logging on next turn. |

---

## 11. Document Citations & Mid-Conversation Caching Innovations

### 1. Native Document Citations Caching
Anthropic's native Citations feature allows passing documents directly via typed blocks:
```python
{
    "type": "document",
    "source": {"type": "text", "media_type": "text/plain", "data": document_content},
    "title": "Telecom Service Specification",
    "citations": {"enabled": True},
    "cache_control": {"type": "ephemeral"}  # Supports prompt caching!
}
```
- **Zero-Token Output Exemption**: In Anthropic's Citations API, `cited_text` tokens inside citations blocks are **100% exempt from billable output tokens** and zero billable tokens in subsequent turns.
- **Prefix Reusability**: Storing static reference documents as cached `document` blocks yields up to a 95% discount across repeated grounding queries.

### 2. Cache-Safe Mid-Conversation System Messages
In Claude 5.x, system instructions can be injected mid-conversation (`role: "system"`). Because prefix caching works sequentially, appending a new system message turn retains the cache hit on all preceding conversation history blocks up to that point.

---

## 12. Official Documentation & References

- **OpenAI Prompt Caching Guide**: https://developers.openai.com/api/docs/guides/prompt-caching
- **OpenAI Latency Optimization Guide**: https://developers.openai.com/api/docs/guides/latency-optimization
- **OpenAI Fast Mode Guide**: https://developers.openai.com/api/docs/guides/fast-mode
- **OpenAI Flex Processing Guide**: https://developers.openai.com/api/docs/guides/flex-processing
- **Anthropic Working with Messages**: https://platform.claude.com/docs/en/build-with-claude/working-with-messages
- **Anthropic Citations & Document Grounding**: https://platform.claude.com/docs/en/build-with-claude/citations
- **Anthropic Prompt Caching Guide**: https://platform.claude.com/docs/en/build-with-claude/prompt-caching
- **Anthropic Effort Controls**: https://platform.claude.com/docs/en/build-with-claude/effort


