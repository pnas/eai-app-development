# Production Error Handling & Rate Limits Cheat Sheet

A battle-tested reference for handling HTTP errors, rate limit quotas, and failure modes when integrating LLM APIs.

---

## 1. Provider HTTP Error Code Taxonomy

| HTTP Code | Root Cause | Is Retryable? | Immediate Recommended Action |
| :--- | :--- | :--- | :--- |
| **`400 Bad Request`** | Invalid parameter, context window exceeded, broken JSON schema, or content safety filter trigger. | **NO** (except context window recovery) | Log error payload. Do **not** retry with the same prompt. If context exceeded, truncate historical turns. |
| **`401 Unauthorized`** | Missing, malformed, or expired API key. | **NO** | Alert immediately; rotate credentials. |
| **`403 Forbidden`** | IP restriction, geographical blockage, or project permission violation. | **NO** | Check provider account tier and IAM permissions. |
| **`404 Not Found`** | Deprecated model ID, deleted batch job, or invalid endpoint URL. | **NO** | Check provider deprecation notices; update model configuration string. |
| **`429 Rate Limit`** | Quota exceeded: Tokens Per Minute (TPM), Requests Per Minute (RPM), or Requests Per Day (RPD). | **YES** | Read `retry-after` header if present. Apply **Exponential Backoff with Full Jitter**. |
| **`500 Internal Error`** | Transient provider-side failure. | **YES** | Retry up to 3 times with exponential backoff. |
| **`502 / 503 Service Unavailable`** | Cloudflare / Gateway edge timeout or infrastructure restart. | **YES** | Retry with jitter; if sustained, trip Circuit Breaker to secondary provider. |
| **`529 Overloaded`** | **Anthropic-specific**: Claude infrastructure is temporarily at maximum capacity. | **YES** | Exponential backoff with jitter or immediate fallback to secondary provider (e.g. GPT-4o). |

---

## 2. Deciphering 429 Rate Limits: RPM vs. TPM

Rate limits are multi-dimensional:
- **RPM (Requests Per Minute)**: Hard cap on concurrent API transactions. Often hit when running unbounded `asyncio.gather()` or `Promise.all()`.
- **TPM (Tokens Per Minute)**: Total prompt tokens + anticipated completion tokens submitted within a 60-second window. A single 100k-token prompt can immediately consume an entire tier quota!
- **RPD (Requests Per Day)**: Daily account-wide limits.

### How Providers Communicate Limits in Headers
```http
# OpenAI Headers
x-ratelimit-limit-requests: 5000
x-ratelimit-remaining-requests: 4892
x-ratelimit-reset-requests: 12ms
x-ratelimit-limit-tokens: 800000
x-ratelimit-remaining-tokens: 725400
x-ratelimit-reset-tokens: 5.2s

# Anthropic Headers
anthropic-ratelimit-requests-limit: 1000
anthropic-ratelimit-requests-remaining: 950
anthropic-ratelimit-tokens-limit: 80000
anthropic-ratelimit-tokens-remaining: 12400
retry-after: 4
```

---

## 3. Resilience Implementation Patterns

### Pattern A: Exponential Backoff with Full Jitter
Never use uniform delays ($1s, 2s, 4s$) because synchronized retries cause a **thundering herd** problem on recovery.

$$\text{sleep\_time} = \text{random}(0, \min(\text{max\_backoff}, \text{base} \cdot 2^{\text{attempt}}))$$

### Pattern B: Circuit Breaker State Machine
```
   [CLOSED]  ──(Consecutive Failures > Threshold)──>  [OPEN]
      ▲                                                  │
      │                                             (Wait TTL)
      │                                                  │
      └───(Probe Request Succeeds)───  [HALF-OPEN]  <────┘
                                            │
                                  (Probe Request Fails)
                                            │
                                            ▼
                                         [OPEN]
```

### Pattern C: Three-Tier Fallback Cascade
1. **Primary**: Anthropic `claude-3-5-sonnet` (Best coding / reasoning quality)
2. **Secondary**: OpenAI `gpt-4o` (High availability, matches tool call format)
3. **Tertiary**: Google `gemini-1.5-flash` (Extreme throughput, massive context window)

