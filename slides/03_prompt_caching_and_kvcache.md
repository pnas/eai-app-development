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

### Anthropic: Explicit Breakpoints
- Uses explicit `cache_control: {"type": "ephemeral"}` blocks.
- Minimum 1,024 tokens (Sonnet) / 2,048 tokens (Haiku). Up to 4 breakpoints.
- **Pricing**: Cache writes cost 1.25x; Cache reads cost **0.10x (90% off)**!
- 5-minute rolling TTL (resets every time cache is hit).

### OpenAI: Automatic Prefix Caching
- Fully automatic for prompts $\ge 1,024$ tokens.
- Matches prefix in 128-token increments.
- **Pricing**: Cache reads cost **0.50x (50% off)**. Standard price on writes.

### Google Gemini: Context Caching
- Explicit cache creation for large documents ($\ge 32k$ tokens) with custom TTL.
- Automatic implicit caching on Gemini 1.5/2.0 models.

---

# 4. What BREAKS the Cache? (Engineering Anti-Patterns)

Prompt caching matches the **exact prefix from token 0**.

1. **Dynamic Timestamps in System Prompts**:
   `"System: You are an agent. Current time: 10:18:34 AM"` $\rightarrow$ **0% Cache Hit Rate!**
2. **Tool Definition Shuffling**:
   If the `tools` array is serialized from an unordered Python set or dictionary, token order changes $\rightarrow$ **Cache Miss**.
3. **Session Identifiers Before Context**:
   `"Session ID: 94a1-b2c3. Here is the 20,000 token documentation..."` $\rightarrow$ **Cache Miss**.
4. **Whitespace and Serialization Jitter**:
   Switching between `\r\n` and `\n` or altering JSON key spacing invalidates the prefix.

---

# 5. The Golden Architecture: Prefix Layering

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
│ 5. Current Turn: Dynamic Time, User Question           │  <-- UNCACHED
└────────────────────────────────────────────────────────┘
```

**Result**: 85%+ lower latency (TTFT) and up to 90% cost savings!

