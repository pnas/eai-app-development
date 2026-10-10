---
marp: true
theme: default
paginate: true
header: "Advanced GenAI Integration | Module 6"
footer: "Enterprise AI Engineering Course"
---

# Module 6: LLM Gateways & Cost Optimization
## LiteLLM, OpenRouter, Virtual Keys & Architectural Trade-offs

---

# 1. The Gateway Value Proposition

As an enterprise grows from 1 to 50 LLM-enabled services:
- **Direct Integration Pain**: 50 microservices each managing separate OpenAI, Anthropic, and Google API keys, retry logic, and billing budgets.
- **The Gateway Layer**: A unified proxy providing:
  - Single OpenAI-compatible wire protocol.
  - Team-level virtual API keys with hard monthly spend quotas.
  - Centralized audit logs and prompt/response tracking.
  - Automated load-balancing and cross-provider failover.

---

# 2. LiteLLM vs. OpenRouter

| Feature | LiteLLM | OpenRouter |
| :--- | :--- | :--- |
| **Hosting Model** | **Self-Hosted** (Docker / Kubernetes / Python) | **Managed Cloud SaaS** |
| **Data Privacy** | 100% inside your VPC; keys never leave your infra | Routed through OpenRouter servers (opt-out available) |
| **Billing Model** | Free open-source; you pay providers directly | Unified credit pool; OpenRouter bills for all models |
| **Key Capability** | Virtual keys, token bucket limits, Redis caching | Dynamic fallback routing (`openrouter/auto`), price discovery |
| **Latency Impact** | ~5ms internal LAN hop | ~50–150ms public internet hop |

---

# 3. Working with LiteLLM in Python

```python
import litellm

# Single entry point for any foundation model
response = litellm.completion(
    model="claude-3-5-sonnet-20241022", # or "gpt-4o" or "gemini/gemini-1.5-pro"
    messages=[{"role": "user", "content": "Analyze architecture"}],
    fallbacks=["gpt-4o", "gemini/gemini-1.5-flash"],
    metadata={"team": "analytics", "environment": "production"}
)
print(response.choices[0].message.content)
```

---

# 4. Architectural Trade-offs to Consider

Before adopting a gateway unconditionally, evaluate the trade-offs:

1. **Feature Lag**:
   - Bleeding-edge provider features (new prompt caching flags, custom audio formats, reasoning effort knobs) may take weeks to land in gateway parsers.
2. **Single Point of Failure**:
   - If your LiteLLM proxy crashes, all LLM traffic across the enterprise halts. Requires HA deployment (Redis + multi-replica containers).
3. **Debugging Abstraction**:
   - Debugging raw provider error messages through an abstraction layer can obscure subtle rate-limit headers.

---

# 5. Enterprise Observability: The Missing Layer

Gateways see HTTP requests, but they are **blind to internal agent decisions**:
- Which tool failed inside a 5-step loop?
- Did the model loop 4 times before deciding on a response?
- Did a sub-agent hallucinate an invalid parameter?

### The Solution: Dual-Telemetry Pipeline
1. **Developer Tracing (LangSmith)**:
   - Deep nested RunTree visualization, prompt evaluation, token heatmaps.
2. **Operational Logging (SIEM / Datadog / Splunk)**:
   - In-band JSON streams, 1–7 year regulatory compliance, security audits.

---

# 6. Tracing (LangSmith) vs. Logging (SIEM)

| Dimension | LangSmith Tracing | Structured Enterprise Logging |
| :--- | :--- | :--- |
| **Primary Audience** | AI Engineers & Prompt Evaluators | SecOps, SRE, and Compliance Officers |
| **Data Format** | Nested RunTree Span Graphs | Flat Newline-Delimited JSON (NDJSON) |
| **Delivery Model** | Asynchronous out-of-band SaaS / VPC | Synchronous in-band stdout / file shipper |
| **Retention** | 14–400 days (tiered) | 1–7 years (audit-proof cold storage) |
| **Query Engine** | Semantic tags & feedback scores | SQL / Lucene / LogQL / KQL |

Both channels run **in parallel via non-invasive callbacks** with zero performance impact.

---

# 7. PII Redaction at the Edge

Enterprise compliance forbids streaming raw customer PII or API credentials:

```python
# Automatic edge scrubbing before disk or network emission:
raw_log = "Customer alice@telekom.de called with token sk-ant-secret123"
clean_log = PIIScrubber.scrub_text(raw_log)

# Result:
"Customer [REDACTED_EMAIL] called with token api_key=\"[REDACTED_CREDENTIAL]\""
```

* Redacts emails, phone numbers, auth bearer tokens, and payment card numbers.
* Implemented identically in Python (`structured_logger.py`) and TypeScript (`structuredLogger.ts`).

---

# 8. OpenTelemetry (OTel) GenAI Standards

Standardize telemetry across all cloud providers using the **OpenTelemetry GenAI Semantic Conventions**:

```json
{
  "name": "gen_ai.chat gpt-4o",
  "attributes": {
    "gen_ai.system": "openai",
    "gen_ai.request.model": "gpt-4o",
    "gen_ai.operation.name": "chat",
    "gen_ai.usage.prompt_tokens": 152,
    "gen_ai.usage.completion_tokens": 48,
    "gen_ai.usage.total_tokens": 200,
    "session.id": "thread-support-991"
  }
}
```

* Plug-and-play export to **OpenTelemetry Collector**, **Jaeger**, **Dynatrace**, and **Google Cloud Trace**.

