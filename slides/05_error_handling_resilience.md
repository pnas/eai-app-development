---
marp: true
theme: default
paginate: true
header: "Advanced GenAI Integration | Module 5"
footer: "Enterprise AI Engineering Course"
---

# Module 5: Error Handling, Rate Limits & Resilience
## HTTP Taxonomy, Jittered Backoff, Circuit Breakers & Fallback Cascades

---

# 1. The HTTP Error Taxonomy & Modern Error Codes

Not all errors are equal. Treating 400 like 429 causes cascading system outages:

| Status Code / Sub-code | Provider Manifestation | Production Strategy |
| :--- | :--- | :--- |
| **`400 Bad Request`** | Invalid param, schema mismatch, or Anthropic sampling constraint violations | **DO NOT RETRY**. Fix payload according to provider capability matrix. |
| **`401 / 403`** | Missing API key, IAM permission denied | **DO NOT RETRY**. Alert DevOps / rotate credentials. |
| **`429 slow_down`** | OpenAI TPM / RPM quota exceeded; Anthropic rate limit | **RETRY with Jittered Backoff** or obey `retry-after` header. |
| **`429 resource_unavailable`** | OpenAI Flex Processing transient capacity constraint | **RETRY with Backoff** or cascade to standard sync tier. |
| **`500 Internal Error`** | Transient gateway or backend failure | **RETRY with Backoff** up to 3 times. |
| **`503 server_is_overloaded` / `529`** | OpenAI cluster capacity shortage or Anthropic overloaded | **CASCADE IMMEDIATELY** to secondary provider (do not wait). |

---

# 2. Why Uniform Retries Cause Outages (Thundering Herd)

```
Time:          T0          T1          T2          T3
Provider:    [Crash]    [Reboots]
Clients:     1,000 reqs ────────► 1,000 retries ──► 1,000 retries (Crashes Again!)
```

### The Solution: Full Jitter Exponential Backoff

$$t = \text{random}(0, \min(\text{max\_backoff}, \text{base} \cdot 2^{\text{attempt}}))$$

Randomizing the sleep duration distributes retries smoothly across the timeline, allowing provider clusters to recover without being hammered simultaneously. Obey the `retry-after` header if present.

---

# 3. The Circuit Breaker Pattern

Prevent downstream services from wasting resources when a provider has an outage:

```
        ┌────────────────────────────────────────────────────────┐
        │                        CLOSED                          │
        │   (Normal operation: all requests pass to provider)    │
        └──────────────────────────┬─────────────────────────────┘
                                   │ Failures > Threshold (e.g. 5)
                                   ▼
        ┌────────────────────────────────────────────────────────┐
        │                         OPEN                           │
        │  (Fast-Fail immediately: route to fallback provider)   │
        └──────────────────────────┬─────────────────────────────┘
                                   │ After Cool-off TTL (e.g. 30s)
                                   ▼
        ┌────────────────────────────────────────────────────────┐
        │                      HALF-OPEN                         │
        │  (Send 1 probe request: if success -> CLOSED, else OPEN│
        └────────────────────────────────────────────────────────┘
```

---

# 4. Multi-Provider Fallback Cascade

Design your architecture to survive single-provider outages:

1. **Primary**: OpenAI GPT-6.1 Sol (`gpt-6.1-sol` - Balanced reasoning, explicit caching & Responses API).
2. **Secondary**: Claude Sonnet 5.5 (`claude-sonnet-5-5` - Superior coding, strict tool schemas & reasoning).
3. **Tertiary**: OpenAI GPT-4.1 (`gpt-4.1` - Fast non-reasoning fallback with speculative decoding).
4. **Quaternary**: Gemini 2.5 Flash (`gemini-2.5-flash` - Ultra-low latency, massive context buffer).

```python
cascade = FallbackCascade([
    OpenAIClient(model="gpt-6.1-sol"),
    ClaudeClient(model="claude-sonnet-5-5"),
    OpenAIClient(model="gpt-4.1"),
    GeminiClient(model="gemini-2.5-flash")
])
response = cascade.execute(prompt)
```

---

# 5. Stateful Agent Resilience: Ephemeral vs. Durable State

What happens when an agent executing a 10-step plan crashes at step 7?

* **Ephemeral Memory (In-Memory lists/dicts)**:
  - Process dies $\to$ entire conversation and intermediate tool outputs are lost.
  - Retrying re-executes steps 1–6 (charging duplicate tokens and risking non-idempotent tool side-effects like duplicate billing).
* **Durable State Machines (LangGraph Checkpointers)**:
  - Every graph transition persists state snapshots to durable storage (`SqliteSaver`, Postgres, Redis).
  - Crashes halt the process; restarting with the same `thread_id` resumes execution exactly at step 7 without re-running earlier steps.

---

# 6. LangGraph Checkpointing & SQLite Recovery

```python
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import StateGraph

# Attach persistent checkpointer to graph compilation
with SqliteSaver.from_conn_string("agent_state.db") as memory:
    app = workflow.compile(checkpointer=memory)
    
    # Thread ID scopes execution history and checkpoint sequence
    config = {"configurable": {"thread_id": "cust-support-4091"}}
    
    # Run step 1: state is atomically saved to SQLite
    app.invoke({"messages": [HumanMessage(content="Check my billing")]}, config)
    
    # Simulating a crash / restart: resume seamlessly
    resumed_state = app.get_state(config)
    print("Resuming from checkpoint:", resumed_state.next)
```

---

# 7. Human-in-the-Loop (HITL) & Safe Resumption

Combine durability with safety gates before dangerous or irreversible actions:

```
[User Request] ──► [Agent Planner] ──► [Inspect Balance]
                                              │
                                              ▼
                                     [PAUSE: HITL Gate]
                                     (Transfer > $1,000?)
                                              │
                          ┌───────────────────┴───────────────────┐
                          ▼                                       ▼
                   [Human Approves]                       [Human Rejects]
                          │                                       │
                          ▼                                       ▼
                  [Execute Refund]                       [Cancel Operation]
```

* Graph stops execution using `interrupt_before=["refund_tool"]`.
* Compliance officer inspects `app.get_state(config)`.
* Officer approves: `app.invoke(None, config)` resumes exactly where it paused.

---

# 8. Enterprise LLM Rate Limiting Architecture (WSO2 AI Gateway)

Why traditional API rate limiting (HTTP requests/sec) fails for Generative AI workloads:

```
Traditional API Gateway:  [ Request 1 ] = 1 unit  |  [ Request 2 ] = 1 unit  (Uniform payload/compute)
LLM / GenAI Gateway:      [ "Hi" (5 tokens) ] vs  [ 100k Token Doc Ingestion + 4k Gen ] (20,000x cost disparity!)
```

### The Three Rate-Limiting Dimensions:
1. **Token Quotas (TPM / TPD)**:
   - **Prompt Token Limit**: Rejects massive payload spam before GPU allocation.
   - **Completion Token Limit**: Limits runaway generation loops and recursive chains.
   - **Total Token Count**: Cumulative window cap (sliding window or leaky bucket).
2. **Cost-Based Quotas ($/window)**:
   - Direct USD spend caps per hour/day calculated in-flight from provider pricing models.
3. **Concurrency & In-Flight Slots**:
   - Long-lived Server-Sent Event (SSE) streams occupy gateway worker threads and upstream sockets.

---

# 9. Token Bucket, Leaky Bucket & GCRA Algorithms

How AI Gateways enforce granular token-aware traffic shaping:

* **Token Bucket**:
  - Capacity $B$ tokens; continuous refill at rate $r$ tokens/sec.
  - Accommodates short bursts while enforcing a strict long-term rate ceiling.
  - Request draws $T_{\text{prompt}} + T_{\text{completion}}$ tokens. If insufficient: returns `HTTP 429`.
* **Leaky Bucket / Sliding Window**:
  - Smooths bursty traffic into a constant output rate; sliding logs track exact timestamps to avoid boundary reset spikes.
* **GCRA (Generic Cell Rate Algorithm)**:
  - Theoretical Arrival Time (TAT) computation enforces continuous spacing between token bursts without Redis atomic lock thrashing.
* **Standard Tracking Headers**:
  ```http
  X-RateLimit-Limit-Tokens: 100000
  X-RateLimit-Remaining-Tokens: 34200
  X-RateLimit-Reset-Tokens: 14s
  Retry-After: 14
  ```

---

# 10. Multi-Tier Governance: Department Chargeback & Virtual Keys

Decoupling client applications from upstream provider quota constraints:

```
[ Team A / Service 1 ] ──(Virtual Key A: 20k TPM, $200/mo)──┐
                                                             ▼
[ Team B / Service 2 ] ──(Virtual Key B: 80k TPM, $1000/mo)─► [ WSO2 / Enterprise Gateway ]
                                                             ▲    │ In-flight Cost Tracking
[ Team C / Batch Job ] ──(Virtual Key C: Off-peak queue)────┘    │ Header Injection
                                                                  ▼
                                                      [ Upstream Foundation Models ]
                                                      (OpenAI / Anthropic / Gemini)
```

- **Subscription-Level Isolation**: High-priority interactive customer bots get dedicated token buckets; background indexing jobs are throttled.
- **Backend Protection vs. Client Quotas**: Gateway throttles clients *before* upstream provider accounts face 429 penalties.
- **Accurate Chargeback**: Real-time token aggregation per department virtual key.

---

# 11. Official Documentation & References

- **WSO2 LLM Rate Limiting Guide**: https://wso2.com/api-platform/learn/llm-rate-limiting/
- **WSO2 AI / LLM Gateway Architecture**: https://wso2.com/api-platform/
- **OpenAI Rate Limits & Tiers**: https://developers.openai.com/api/docs/guides/rate-limits
- **OpenAI Error Handling & Codes**: https://developers.openai.com/api/docs/guides/error-codes
- **Anthropic Working with Messages & Errors**: https://platform.claude.com/docs/en/build-with-claude/working-with-messages
- **Anthropic Effort & Reasoning Controls**: https://platform.claude.com/docs/en/build-with-claude/effort

