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

```
                ANTHROPIC                       OPENAI                       GOOGLE GEMINI
Strategy:       Explicit Breakpoints            Automatic Prefix Matching    Explicit & Implicit Caching
Syntax:         cache_control: {type: ephemeral}Automatic (>=1024 tokens)    CachedContent resource / automatic
Min Tokens:     1,024 (Sonnet) / 2,048 (Haiku)   1,024 tokens                 32,768 tokens (explicit)
Block Step:     Per designated block            128-token increments         Configurable chunks
Read Discount:  90% off input price             50% off input price          75% off input price
Write Cost:     125% of input price             Standard input price (100%)  Free write + storage per hour
```

---

## 3. The 6 Deadly Sins: What Silently Breaks the Cache?

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

### ❌ Invalidation 5: Falling Below the Minimum Token Threshold
- OpenAI requires $\ge 1,024$ tokens for automatic caching. A prompt with 980 tokens will **never** be cached.
- Anthropic requires $\ge 1,024$ tokens on Claude 3.5 Sonnet and $\ge 2,048$ tokens on Claude 3.5 Haiku.

### ❌ Invalidation 6: Anthropic 4-Breakpoint Exhaustion
- Anthropic permits a maximum of **4** `cache_control` blocks in a single request.
- If you place 5 `cache_control: {"type": "ephemeral"}` tags, the API returns a `400 Bad Request`.

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

