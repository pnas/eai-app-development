---
marp: true
theme: default
paginate: true
header: "Advanced GenAI Integration | Module 3"
footer: "Enterprise AI Engineering Course"
---

# Module 3: Prompt Caching & The KV-Cache Deep Dive
## GPU Attention Mechanics, Vendor Implementations & Cache-Breaking Pitfalls

---

# 1. GPU Attention & The KV-Cache

To master prompt caching, you must understand what happens inside GPU VRAM:

- **Transformer Attention**: Computes $Q \cdot K^T / \sqrt{d_k} \times V$ across all tokens.
- **Prefill Stage**: Takes $N$ prompt tokens, runs $O(N^2)$ quadratic matrix math, and saves Key ($K$) and Value ($V$) activation vectors.
- **Decoding Stage**: Autoregressively generates new tokens one-by-one by querying the existing $K,V$ memory blocks in VRAM.

**PagedAttention**: Modern serving engines (vLLM, TensorRT-LLM) allocate GPU memory for KV-cache in fixed-size blocks (like virtual memory pages) rather than contiguous tensors.

---

# 2. KV-Cache vs. API Prompt Caching

| Dimension | GPU-Level KV-Cache | API-Level Prompt Caching |
| :--- | :--- | :--- |
| **Scope** | Single model process / instance | Distributed across multi-tenant cluster |
| **Storage Medium** | High-Bandwidth GPU VRAM | Tiered: VRAM $\rightarrow$ Host RAM $\rightarrow$ NVMe SSD |
| **Matching Algorithm** | Exact token pointer in memory | Exact prefix cryptographic hash |
| **Persistence** | Lifetime of generation request | 5 min to 1+ hours across independent requests |
| **Financial Benefit** | Server throughput (tokens/sec) | **50% to 90% direct billing discount** |

---

# 3. Provider Implementations Compared

### Anthropic Claude (Opus 5.5 / Sonnet 5.5 / Haiku 5.5 / 5.x): Explicit & Native Caching
- **Dual Placement**: Explicit `cache_control: {"type": "ephemeral"}` blocks OR top-level request auto-caching (consumes 1 of 4 breakpoint slots).
- **Thresholds & Window**: **1,024 tokens** (Opus 5.5 / Sonnet 5.5 / Opus 5 / 5.x) | **2,048 tokens** (Haiku 5.5). Prefix matching looks back at most **20 blocks** (consecutive tool blocks count as 1 position).
- **Document Block Caching**: Native citation `document` blocks (`{"type": "document", ...}`) support `cache_control: {"type": "ephemeral"}`. Cited text tokens are 100% exempt from billable output tokens!
- **TTL Options**: **5-minute rolling TTL** (default, 1.25x write surcharge) or **1-hour extended TTL** (`"ttl": "1h"`, 2.0x write surcharge).
- **Pricing & Discounts**: Claude Haiku 5.5 / Sonnet 5.5 / Opus 5.5 cached reads cost **0.05x to 0.10x (90%–95% off)**; Mythos 5.1 costs **0.025x (97.5% off)**!
- **Cache-Safe Mid-Conversation Messages**: Claude 5.x supports mid-conversation `role: "system"` messages that do not invalidate earlier cached history blocks.

### OpenAI: Dual Generational Architecture
- **Classic Models (GPT-4o, GPT-4o-mini, o1, o3-mini)**:
  - Automatic prefix matching $\ge 1,024$ tokens in **128-token increment blocks**.
  - **Pricing**: 50% read discount (0.50x); 0% write surcharge (1.00x).
- **Modern Models (GPT-5.6+, GPT-6, GPT-6.1 Sol / Responses API)**:
  - **Dual Mode**: `explicit` breakpoints (up to 4 write slots; suffix billed at standard rate) or `implicit`.
  - **Pricing**: 1.25x write surcharge; **90% read discount** (95% / 0.05x on GPT-6.1 Sol).
  - **Prewarming**: `prewarm: true` prepares KV-cache without generating tokens.
  - **TTL & Security**: Rolling 30-min TTL (`ttl: "30m"`); `prompt_cache_key` isolates tenant accounting & blocks cache probing.

### Google Gemini (Enterprise Agent Platform): Context Caching
- **Dual Mode**:
  - **Implicit Caching**: Default on GCP. **90% discount** on cached tokens; **$0.00 storage fee**.
  - **Explicit Caching**: Manual `CachedContent` API with customizable TTL (default 60m).
- **Thresholds**: Gemini 2 $\ge$ 2,048 tokens | Gemini 3 $\ge$ 4,096 tokens (6,144 for 3.7/3.8 Flash preview).
- **Enterprise Isolation**: Scoped by GCP project ID, VPC-SC support, execution-context scoping.

---

# 4. Prompt Cache Diagnostics & Monitoring (OpenAI & Anthropic)

### Automated Miss Root-Cause Analysis
Both OpenAI and Anthropic now support programmatic attribution when prompt caches miss:

| Diagnostic Feature | OpenAI Responses API | Anthropic Claude Messages API |
| :--- | :--- | :--- |
| **Opt-In Parameter** | `prompt_cache_options.comparison_response_id` | `diagnostics: {"previous_message_id": "msg_..."}` |
| **Response Field** | `response.prompt_cache_diagnostics` | `response.cache_miss_reason` |
| **Core Reason Codes** | `tools_changed`, `model_changed`, `prompt_cache_key_changed`, `input_changed`, `reasoning_effort_changed` | `system_changed`, `tools_changed`, `messages_changed`, `model_changed`, `previous_message_not_found`, `unavailable` |
| **Missed Tokens Telemetry** | `cache_missed_tokens`, `comparison_reusable_tokens` | `cache_missed_input_tokens` |

### Telemetry & Monitoring Formulas
- **Token Cache Hit Rate**: $H_T = \frac{\text{cached\_tokens}}{\text{input\_tokens}} \times 100\%$ (Target $\ge 80\%$; alert if $< 50\%$).
- **Weighted Input Cost**: $C_{\text{input}} = \frac{(T_{\text{ordinary}} + T_{\text{cached}} \cdot r + T_{\text{write}} \cdot w) \cdot P_{\text{million}}}{1{,}000{,}000}$

---

# 5. What BREAKS the Cache? (Engineering Anti-Patterns)

Prompt caching matches the **exact prefix from token 0**.

1. **Dynamic Timestamps in System Prompts**:
   `"System: You are an agent. Current time: 10:18:34 AM"` $\rightarrow$ **0% Cache Hit Rate!**
2. **Tool Definition Shuffling**:
   If the `tools` array is serialized from an unordered Python set or dictionary, token order changes $\rightarrow$ **Cache Miss**.
3. **Session Identifiers Before Context**:
   `"Session ID: 94a1-b2c3. Here is the 20,000 token documentation..."` $\rightarrow$ **Cache Miss**.
4. **Whitespace and Serialization Jitter**:
   Switching between `\r\n` and `\n` or altering JSON key spacing invalidates the prefix.
5. **Breakpoint Exhaustion**:
   Adding $>4$ breakpoints on Anthropic or OpenAI explicit mode triggers errors or fallback.

---

# 6. The Golden Architecture: Prefix Layering

Structure all multi-turn and agent prompts in this strict order:

```
┌────────────────────────────────────────────────────────┐
│ 1. Static System Instructions (Rules, Personas)        │  <-- CACHED (Breakpoint 1)
├────────────────────────────────────────────────────────┤
│ 2. Tool Schemas (Deterministically Sorted by Name)     │  <-- CACHED (Breakpoint 2)
├────────────────────────────────────────────────────────┤
│ 3. Static Context / Large Documents (10,000+ tokens)   │  <-- CACHED (Breakpoint 3)
├────────────────────────────────────────────────────────┤
│ 4. Conversation History (Older turns)                  │  <-- CACHED (Breakpoint 4 - Rolling)
├────────────────────────────────────────────────────────┤
│ 5. Current Turn: Dynamic Time, User Question           │  <-- UNCACHED (Fresh Tokens)
└────────────────────────────────────────────────────────┘
```

**Result**: 85%+ lower latency (TTFT) and up to 90%–95% cost savings!

---

# 7. Prompt Caching Economics & Financial Break-Even

| Scenario (Base Token Cost = $P$) | 1 Request (Cold) | 2 Requests | 10 Requests | Break-Even Point |
| :--- | :--- | :--- | :--- | :--- |
| **No Caching** | $1.00 \times P$ | $2.00 \times P$ | $10.00 \times P$ | Baseline |
| **Anthropic 5m TTL (1.25x write, 0.10x read)** | $1.25 \times P$ | **$1.35 \times P$ (-32.5%)** | **$2.15 \times P$ (-78.5%)** | **Turn 2** |
| **Anthropic 1h TTL (2.00x write, 0.10x read)** | $2.00 \times P$ | **$2.10 \times P$ (invest)** | **$2.90 \times P$ (-71.0%)** | **Turn 3** (avoids repeated cold writes) |
| **Anthropic Sonnet 5.5 (1.25x write, 0.05x read)** | $1.25 \times P$ | **$1.30 \times P$ (-35.0%)** | **$1.70 \times P$ (-83.0%)** | **Turn 2** |
| **OpenAI Classic (1.00x write, 0.50x read)** | $1.00 \times P$ | **$1.50 \times P$ (-25.0%)** | **$5.50 \times P$ (-45.0%)** | **Turn 2** |
| **OpenAI Modern (1.25x write, 0.10x read)** | $1.25 \times P$ | **$1.35 \times P$ (-32.5%)** | **$2.15 \times P$ (-78.5%)** | **Turn 2** |
| **OpenAI GPT-6.1 Sol (1.25x write, 0.05x read)**| $1.25 \times P$ | **$1.30 \times P$ (-35.0%)** | **$1.70 \times P$ (-83.0%)** | **Turn 2** |
| **Gemini Implicit (1.00x write, 0.10x read)** | $1.00 \times P$ | **$1.10 \times P$ (-45.0%)** | **$1.90 \times P$ (-81.0%)** | **Turn 2** |

---

# 8. The Minimum Cacheable Length Cost Trap

### When is force-padding a short prompt to 1,024 tokens profitable?

When a write surcharge exists ($w = 1.25, r = 0.10$), padding length $L < M$ up to $M$ is only accretive if:
$$L \ge L_{\mathrm{break\text{-}even}} = M \left( r + \frac{w - r}{N} \right)$$

- At $N = 2$ reuses: $L_{\text{break-even}} = \mathbf{691\text{ tokens}}$ (Do NOT pad if $L < 691$)
- At $N = 5$ reuses: $L_{\text{break-even}} = \mathbf{338\text{ tokens}}$
- At $N = 10$ reuses: $L_{\text{break-even}} = \mathbf{220\text{ tokens}}$
- At $N \rightarrow \infty$ reuses: $L_{\text{break-even}} \rightarrow \mathbf{102\text{ tokens}}$

> **Golden Rule**: Never pad prompts shorter than **220 tokens** unless guaranteed $\ge 10$ reuses within the TTL window!
 
---

# 9. OpenAI Dual-Mode Caching, Lookup Boundaries & Suffix Protection

### Explicit Breakpoints vs. Implicit Boundary Detection (Responses API)
- **Explicit Mode (`prompt_cache_options.mode: "explicit"`)**:
  - Developers place explicit breakpoints on specific content items: `prompt_cache_breakpoint: {"mode": "explicit"}`.
  - Supports up to **4 write slots** per request.
  - **Suffix Cost Protection**: Uncached content placed after the final explicit breakpoint is billed at the standard 1.00x rate, completely avoiding the 1.25x write surcharge!
- **Implicit Mode (`prompt_cache_options.mode: "implicit"`)**:
  - Automatically identifies candidate boundaries: latest user turn, last tool result in a group, and last developer message in initial block.

### Lookup Boundaries Scanning Algorithm
- **Backward Scanning**: Evaluates prefixes in reverse order, from **longest to shortest prefix**.
- **Explicit Scan Candidate Set**: Tests the **first 2** and the **latest 50** explicit breakpoints in the request.
- **Implicit Scan Candidate Set**: Tests the first 2 + latest 50 explicit breakpoints + current implicit breakpoint + up to **20 earlier eligible message endings**.

---

# 10. Physical Machine Affinity, Overflow Routing & Multi-Tenant Security

### The Physical Reality of KV Caches
- **In-Memory Storage**: KV tensors reside in GPU VRAM and host RAM on **specific physical machines** within the inference cluster.
- **Traffic Overflow Routing (~15 RPM Threshold)**:
  - If a single prompt cache key / prefix receives heavy concurrent traffic (typically **> 15 requests/minute**), OpenAI load balancers automatically route surplus traffic to alternative physical machines.
  - **Result**: You will observe initial cache write surcharges (1.25x) on secondary nodes until their local caches warm up, despite identical input prefixes!

### The Strategic Role of `prompt_cache_key`
- **Legacy / Earlier Models (GPT-4o, GPT-5.5)**:
  - Directs related traffic to the exact same physical machine to maximize cache hits.
- **Modern Architectures (GPT-5.6+, GPT-6)**:
  - Routing is automated globally. `prompt_cache_key` isolates **tenant accounting & billing boundaries**.
  - **Cache-Hit Probing Defense**: Blocks timing/side-channel attacks where an adversary tries to discover whether another tenant has previously processed confidential documents.

---

# 11. Enterprise Cache Operations: Prewarming, Config Updates & Pitfalls

### Cache Prewarming (`prewarm: true`)
- **Zero-Token Cache Building**: Submits large static runbooks, schemas, or enterprise catalogs to populate GPU memory ahead of time without generating completion tokens.
- **Eliminates Cold Starts**: First end-user request hits warm KV memory, reducing Time-To-First-Token (TTFT) by up to 85%.

### Dynamic Mid-Conversation Configuration Updates
- Pass `{"type": "configuration_update", "reasoning": {"effort": "high"}}` as an input item.
- Modifies reasoning effort or generation parameters without rewriting or invalidating preceding cached conversational turns!

### Three Critical Engineering Pitfalls
1. **The Message Extension Pitfall**: Extending `Turn N: "Content A"` to `"Content A + Content B"` moves the message ending boundary. Implicit caching cannot match Turn N unless an explicit breakpoint was set at boundary A!
2. **Mode Switching Miss**: Switching from `mode: "implicit"` to `mode: "explicit"` across turns misses implicit writes.
3. **TPM Rate Limit Inelasticity**: Cached tokens receive financial discounts, but still consume **100% of your Tokens-Per-Minute (TPM)** quota!

---

# 12. Official Documentation & References

- **OpenAI Prompt Caching Guide**: https://developers.openai.com/api/docs/guides/prompt-caching
- **OpenAI Latency Optimization**: https://developers.openai.com/api/docs/guides/latency-optimization
- **OpenAI Fast Mode Guide**: https://developers.openai.com/api/docs/guides/fast-mode
- **OpenAI Flex Processing Guide**: https://developers.openai.com/api/docs/guides/flex-processing
- **Anthropic Prompt Caching Guide**: https://platform.claude.com/docs/en/build-with-claude/prompt-caching
- **Anthropic Working with Messages**: https://platform.claude.com/docs/en/build-with-claude/working-with-messages
- **Anthropic Citations & Document Caching**: https://platform.claude.com/docs/en/build-with-claude/citations
- **Anthropic Effort Controls**: https://platform.claude.com/docs/en/build-with-claude/effort


