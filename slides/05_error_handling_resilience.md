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

