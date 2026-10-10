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
- **Anthropic**: Constrained schema via forced tool call.

---

# 3. Provider Implementations

### OpenAI Strict JSON Schema
```python
client.beta.chat.completions.parse(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Extract customer data..."}],
    response_format=CustomerRecord,  # Pydantic v2 Model
)
```
*Note: OpenAI requires `"additionalProperties": false` across all nested objects.*

### Google Gemini Structured Outputs
```python
client.models.generate_content(
    model="gemini-1.5-pro",
    contents="Extract customer data...",
    config=types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=CustomerRecord
    )
)
```

---

# 4. Anthropic Structured Output Pattern

Anthropic Claude natively supports constrained tool-use:

```python
response = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=1024,
    tools=[{
        "name": "record_customer",
        "description": "Record structured customer profile",
        "input_schema": CustomerRecord.model_json_schema()
    }],
    tool_choice={"type": "tool", "name": "record_customer"},
    messages=[{"role": "user", "content": "Extract customer data..."}]
)
# Result is guaranteed to be in response.content[0].input
```

---

# 5. Remaining Edge Cases & The Self-Repair Loop

Even with constrained decoding, two production issues remain:

1. **Max Output Token Truncation**:
   - If output hits `max_tokens` mid-stream, generation halts immediately, cutting off the JSON.
   - **Detection**: Check `finish_reason == "length"` (or `"max_tokens"`).
2. **Semantic Failure**:
   - The JSON is syntactically valid, but business logic fails (e.g. invalid IBAN or impossible dates).

**The Self-Repair Loop**:
Feed the partial output and the validation error back to the model with an explicit instruction to continue/repair the schema.

