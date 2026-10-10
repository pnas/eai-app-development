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

