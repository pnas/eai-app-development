# Production Error Handling & Rate Limits Cheat Sheet

A battle-tested reference for handling HTTP errors, rate limit quotas, and failure modes when integrating LLM APIs.

---

## 1. Provider HTTP Error Code Taxonomy

| HTTP Code / Sub-code | Root Cause | Is Retryable? | Immediate Recommended Action |
| :--- | :--- | :--- | :--- |
| **`400 Bad Request`** | Invalid parameter, context window exceeded, broken JSON schema, or content safety trigger.<br>**Anthropic Specific 400 Violations**:<br>• Passing `temperature`, `top_p`, or `top_k` to Claude 4.7+ / 5.x<br>• Response prefilling on Claude 4.6+<br>• Combining Structured Outputs with Citations<br>• Exceeding 4 `cache_control` breakpoints | **NO** (except context window recovery) | Log error payload. Do **not** retry with the same prompt. Fix parameter incompatibility according to provider matrix. |
| **`401 Unauthorized`** | Missing, malformed, or expired API key. | **NO** | Alert immediately; rotate credentials. |
| **`403 Forbidden`** | IP restriction, geographical blockage, or project permission violation. | **NO** | Check provider account tier and IAM permissions. |
| **`404 Not Found`** | Deprecated model ID, deleted batch job, or invalid endpoint URL. | **NO** | Check provider deprecation notices; update model configuration string. |
| **`429 slow_down`** | OpenAI TPM / RPM quota exceeded; standard rate limit. | **YES** | Read `retry-after` header if present. Apply **Exponential Backoff with Full Jitter**. |
| **`429 resource_unavailable`** | OpenAI Flex Processing transient capacity constraint. | **YES** | Exponential backoff or cascade to standard sync tier (`service_tier: "default"`). |
| **`500 Internal Error`** | Transient provider-side failure. | **YES** | Retry up to 3 times with exponential backoff. |
| **`502 / 503 Service Unavailable`** | Gateway edge timeout or infrastructure restart. | **YES** | Retry with jitter; if sustained, trip Circuit Breaker to secondary provider. |
| **`503 server_is_overloaded`** | **OpenAI cluster capacity constraint**: Server is temporarily unable to handle request volume. | **YES** (with cascade) | Cascade immediately to secondary provider or failover model. |
| **`529 Overloaded`** | **Anthropic-specific**: Claude infrastructure is temporarily at maximum capacity. | **YES** (with cascade) | Exponential backoff with jitter or immediate fallback to secondary provider (e.g. `gpt-6.1-sol`). |

---

## 2. Deciphering 429 Rate Limits: RPM, TPM & Ramp-Up Rates

Rate limits are multi-dimensional:
- **RPM (Requests Per Minute)**: Hard cap on concurrent API transactions. Often hit when running unbounded `asyncio.gather()` or `Promise.all()`.
- **TPM (Tokens Per Minute)**: Total prompt tokens + anticipated completion tokens submitted within a 60-second window. A single 100k-token prompt can immediately consume an entire tier quota!
- **Fast Mode Ramp-Up Limits**: Under `service_tier: "fast"`, models enforce a ramp-up rate: **1,000,000 TPM baseline**, increasing by **+50% every 15 minutes** of sustained traffic. Rapid spikes exceeding the ramp envelope return `429 slow_down`.
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
retry-after: 4

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

### Pattern C: Four-Tier Fallback Cascade
1. **Primary**: OpenAI `gpt-6.1-sol` (Balanced reasoning, Responses API, explicit prompt caching)
2. **Secondary**: Anthropic `claude-sonnet-5-5` (Superior coding quality, strict tools)
3. **Tertiary**: OpenAI `gpt-4.1` (Fast non-reasoning fallback with speculative decoding)
4. **Quaternary**: Google `gemini-2.5-flash` (Extreme throughput, massive context window)

### Pattern D: Enterprise Token-Aware Rate Limiting (WSO2 LLM Gateway Pattern)
Standard API gateways limit purely by Request Per Minute (RPM), which fails in GenAI due to token variance. Enterprise LLM Gateways (such as WSO2 AI Gateway) implement multi-dimensional traffic shaping:
1. **Prompt Token Ceilings**: Pre-validate incoming prompt token count before dispatching to GPU clusters.
2. **Completion Token Reservation**: Allocate speculative completion allowances, tracking real usage post-generation.
3. **Token Bucket & GCRA (Generic Cell Rate Algorithm)**: Continuously refill token capacity at rate $r$ tokens/sec to allow burst tolerance up to bucket size $B$ while preventing upstream provider exhaustion.
4. **Department Chargeback & Virtual Key Quotas**: Map requests to team-specific token quotas and budget caps ($/window) with real-time tracking headers (`X-RateLimit-Limit-Tokens`, `X-RateLimit-Remaining-Tokens`, `Retry-After`).

---

## 4. Official Documentation & References

- **WSO2 LLM Rate Limiting**: https://wso2.com/api-platform/learn/llm-rate-limiting/
- **WSO2 AI Platform**: https://wso2.com/api-platform/
- **OpenAI Rate Limits & Tiers**: https://developers.openai.com/api/docs/guides/rate-limits
- **OpenAI Latency Optimization**: https://developers.openai.com/api/docs/guides/latency-optimization
- **OpenAI Fast Mode**: https://developers.openai.com/api/docs/guides/fast-mode
- **OpenAI Flex Processing**: https://developers.openai.com/api/docs/guides/flex-processing
- **Anthropic Working with Messages & Errors**: https://platform.claude.com/docs/en/build-with-claude/working-with-messages
- **Anthropic Effort & Reasoning Controls**: https://platform.claude.com/docs/en/build-with-claude/effort
- **Anthropic Streaming & Exceptions**: https://platform.claude.com/docs/en/build-with-claude/streaming


