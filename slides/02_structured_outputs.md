---
marp: true
theme: default
paginate: true
header: "Advanced GenAI Integration | Module 2"
footer: "Enterprise AI Engineering Course"
---

# Module 2: The Response API & Structured Outputs
## Grammar Constraints, JSON Schemas & Self-Repair Patterns

---

# 1. Why Unconstrained JSON Fails in Production

Before 2024, engineers relied on prompt engineering for JSON:
- *"Respond ONLY with valid JSON matching this schema: {...}"*

**Failure Modes Experienced in Production**:
- Hallucinated markdown wrappers (` ```json \n {...} \n ``` `).
- Trailing commas, single quotes, or missing closing brackets.
- Missing required keys or unexpected data types (`"age": "thirty"`).
- Non-deterministic schema drift over time.

---

# 2. The Solution: Constrained Decoding (Grammars)

Modern Response APIs utilize **Context-Free Grammar (CFG) constrained decoding**:

```
Model Output Logits (Vocabulary: 100k+ tokens)
      │
      ▼
┌────────────────────────────────────────────────────────┐
│ Masking Engine: Logits checked against JSON Grammar   │
│ Any token violating the schema receives -Infinity logit│
└────────────────────────────────────────────────────────┘
      │
      ▼
Only Syntactically Valid Tokens Can Physically Be Sampled!
```

- **OpenAI**: Strict Structured Outputs (`strict: true`).
- **Google Gemini**: `response_schema` with grammar guidance.
- **Anthropic**: Native Structured Outputs (`output_config.format` & `client.messages.parse`) plus strict tool calling (`strict: true`).

---

# 3. Provider Implementations (OpenAI & Gemini)

### OpenAI Responses API & Chat Completions Strict JSON
```python
# Modern Responses API (gpt-6.1-sol / gpt-4.1)
response = client.responses.create(
    model="gpt-6.1-sol",
    input="Extract customer record from: Alice Smith, 34, engineer in Berlin",
    response_format={
        "type": "json_schema",
        "json_schema": {"name": "CustomerRecord", "strict": True, "schema": CustomerRecord.model_json_schema()}
    }
)

# Chat Completions SDK parse helper (gpt-4.1 / gpt-4o)
completion = client.beta.chat.completions.parse(
    model="gpt-4.1",
    messages=[{"role": "user", "content": "Extract customer data..."}],
    response_format=CustomerRecord,  # Pydantic v2 Model
)
```
*Note: OpenAI requires `"additionalProperties": false` across all nested object definitions.*

### Google Gemini Structured Outputs
```python
client.models.generate_content(
    model="gemini-3.8-flash",
    contents="Extract customer data...",
    config=types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=CustomerRecord
    )
)
```

---

# 4. Predicted Outputs: Speculative Structured Updates

When updating existing code or large JSON payloads, most tokens remain identical:

```python
# OpenAI Predicted Outputs (gpt-4.1 / gpt-4o)
completion = client.chat.completions.create(
    model="gpt-4.1",
    messages=[
        {"role": "user", "content": "Update user email to alice@newcorp.com:\n" + original_json}
    ],
    response_format={"type": "json_object"},
    prediction={
        "type": "content",
        "content": original_json  # Model speculatively validates existing tokens
    }
)
```

**Why This Matters for Structured Latency**:
- **Speculative Decoding**: The model verifies matching tokens in parallel rather than sampling autoregressively token-by-token.
- **Latency Acceleration**: 2x to 4x reduction in total completion latency for edits/refactoring.
- **Token Accounting**:
  - `usage.completion_tokens_details.accepted_prediction_tokens`: Tokens successfully verified.
  - `usage.completion_tokens_details.rejected_prediction_tokens`: Modified/divergent tokens.
  - Compatible with SSE streaming!

---

# 5. Anthropic Native Structured Outputs Pattern

Claude supports native JSON Schema extraction via SDK `parse` or `output_config.format`:

```python
# 1. Native Typed Extraction via SDK parse helper (Pydantic v2)
response = client.messages.parse(
    model="claude-sonnet-5-5",
    max_tokens=1024,
    output_format=CustomerRecord,
    messages=[{"role": "user", "content": "Extract customer data..."}]
)
customer: CustomerRecord = response.parsed_output

# 2. Wire Protocol via output_config.format
response = client.messages.create(
    model="claude-sonnet-5-5",
    max_tokens=1024,
    output_config={"format": {"type": "json_schema", "schema": CustomerRecord.model_json_schema()}},
    messages=[{"role": "user", "content": "Extract customer data..."}]
)
```

> [!NOTE] Architectural Guardrails
> - **Grammar Caching**: Anthropic caches compiled JSON schema grammars for **24 hours**.
> - **Strict Tools**: Tools support `"strict": true` with `"additionalProperties": false`.
> - **Incompatibility**: Structured outputs **cannot** be combined with Citations or Message Prefilling (returns HTTP 400).

---

# 6. Remaining Edge Cases & The Self-Repair Loop

Even with constrained decoding, two production issues remain:

1. **Max Output Token Truncation**:
   - If output hits `max_tokens` mid-stream, generation halts immediately, cutting off the JSON.
   - **Detection**: Check `finish_reason == "length"` (or `"max_tokens"`).
2. **Semantic Failure**:
   - The JSON is syntactically valid, but business logic fails (e.g. invalid IBAN or impossible dates).

**The Self-Repair Loop**:
Feed the partial output and the validation error back to the model with an explicit instruction to continue/repair the schema.


