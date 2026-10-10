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

# 1. The HTTP Error Taxonomy

Not all errors are equal. Treating 400 like 429 causes cascading system outages:

| Status Code | Description | Strategy |
| :--- | :--- | :--- |
| **`400 Bad Request`** | Invalid param, context length exceeded, content filter | **DO NOT RETRY**. Truncate context or fix payload. |
| **`401 / 403`** | Missing API key, IAM permission denied | **DO NOT RETRY**. Alert DevOps / rotate key. |
| **`429 Rate Limit`** | TPM / RPM / RPD quota exceeded | **RETRY with Jittered Backoff** or switch provider. |
| **`500 / 503`** | Provider internal server error | **RETRY with Backoff** up to 3 times. |
| **`529 Overloaded`** | Anthropic infrastructure capacity exceeded | **RETRY with Backoff** or cascade to secondary. |

---

# 2. Why Uniform Retries Cause Outages (Thundering Herd)

```
Time:          T0          T1          T2          T3
Provider:    [Crash]    [Reboots]
Clients:     1,000 reqs ────────► 1,000 retries ──► 1,000 retries (Crashes Again!)
```

### The Solution: Full Jitter Exponential Backoff

$$t = \text{random}(0, \min(\text{max\_backoff}, \text{base} \cdot 2^{\text{attempt}}))$$

Randomizing the sleep duration distributes retries smoothly across the timeline, allowing provider clusters to recover without being hammered simultaneously.

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

1. **Primary**: Claude 3.5 Sonnet (Superior coding / reasoning).
2. **Secondary**: GPT-4o (High availability, similar tool calling format).
3. **Tertiary**: Gemini 1.5 Flash (Ultra-low latency, massive 1M context buffer).

```python
cascade = FallbackCascade([
    ClaudeClient(model="claude-3-5-sonnet"),
    OpenAIClient(model="gpt-4o"),
    GeminiClient(model="gemini-1.5-flash")
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

