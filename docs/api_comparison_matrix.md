# Comprehensive GenAI Provider API Comparison Matrix

A production engineering comparison between **OpenAI**, **Anthropic**, and **Google Gemini** as of 2026.

---

## 1. Core Architectural & Protocol Differences

| Feature | OpenAI | Anthropic | Google Gemini |
| :--- | :--- | :--- | :--- |
| **Primary Models** | `gpt-4o`, `gpt-4o-mini`, `o1`, `o3-mini` | `claude-3-5-sonnet`, `claude-3-5-haiku`, `claude-3-opus` | `gemini-1.5-pro`, `gemini-1.5-flash`, `gemini-2.0-flash` |
| **Official Python SDK** | `openai` (`OpenAI`, `AsyncOpenAI`) | `anthropic` (`Anthropic`, `AsyncAnthropic`) | `google-genai` (`Client`) |
| **Official TypeScript SDK**| `openai` | `@anthropic-ai/sdk` | `@google/genai` |
| **Message Hierarchy** | Flat array: `[{role: "system" \| "developer" \| "user" \| "assistant" \| "tool", content: ...}]` | Top-level `system: "..."` parameter; `messages: [{role: "user" \| "assistant", content: ...}]` | `contents: [{role: "user" \| "model", parts: [...]}]`; `system_instruction` at top level |
| **Content Blocks** | String or Array of `{type: "text" \| "image_url"}` | Polymorphic Array of `{type: "text" \| "image" \| "tool_use" \| "tool_result"}` | Array of `parts: [{text: "..."}, {inline_data: {...}}, {function_call: {...}}, {function_response: {...}}]` |
| **Streaming Protocol** | Server-Sent Events (SSE) with `ChatCompletionChunk` (`choices[0].delta.content`) | SSE with typed event stream: `message_start`, `content_block_start`, `content_block_delta`, `message_delta` | Chunk stream via `client.models.generate_content_stream()`, emitting `GenerateContentResponse` |
| **Tool Calling Wire Format**| `tools: [{type: "function", function: {name, description, parameters}}]` | `tools: [{name, description, input_schema}]` | `tools: [{function_declarations: [{name, description, parameters}]}]` |
| **Forced Tool Choice** | `tool_choice: "required"` or `{"type": "function", "function": {"name": "..."}}` | `tool_choice: {"type": "tool", "name": "..."}` or `{"type": "any"}` | `tool_config: {function_calling_config: {mode: "ANY" \| "AUTO" \| "NONE"}}` |

---

## 2. Structured Outputs & Constrained Decoding

| Feature | OpenAI | Anthropic | Google Gemini |
| :--- | :--- | :--- | :--- |
| **Guaranteed Schema Enforcement** | `response_format: { type: "json_schema", json_schema: { strict: true, schema: ... } }` | Coerced via single tool with `tool_choice: {"type": "tool", "name": "schema_tool"}` | `response_mime_type: "application/json"`, `response_schema: PydanticModel` |
| **Underlying Mechanism** | Context-Free Grammar (CFG) constrained decoding (logit masking) | Constrained decoding via tool parser | Constrained decoding schema engine |
| **Pydantic v2 Support** | Direct via `client.beta.chat.completions.parse(..., response_format=Model)` | Converted to JSON schema via tool definition | Direct via `config=types.GenerateContentConfig(response_schema=Model)` |
| **Handling Extra Fields** | Requires `"additionalProperties": false` on all object schemas | Enforced through JSON schema definition in tool | Enforced through schema definition |

---

## 3. Prompt Caching & Memory Reuse

| Dimension | OpenAI | Anthropic | Google Gemini |
| :--- | :--- | :--- | :--- |
| **Mechanism** | **Automatic Prefix Caching** | **Explicit Breakpoints (`cache_control`)** | **Explicit Context Caching & Implicit Caching** |
| **Activation Threshold** | Minimum 1,024 tokens | Minimum 1,024 tokens (Claude 3.5 Sonnet) / 2,048 tokens (Haiku) | Minimum 32,768 tokens (explicit cache) |
| **Control Granularity** | Automatic prefix matching in 128-token increments | Up to 4 explicit breakpoints (`{"type": "ephemeral"}`) | Explicit named cached content resource with configurable TTL |
| **TTL (Time to Live)** | Rolling TTL (typically 5–10 min of inactivity) | Rolling 5-minute TTL (resets upon cache read) | User-defined TTL (e.g. 1 hour, 1 day) or auto-expires |
| **Cost: Cache Write** | Standard input price (1.0x) | **1.25x** standard input price | Free write, storage fee per hour for active TTL |
| **Cost: Cache Read (Hit)**| **50% discount** (0.5x) | **90% discount** (0.1x) | **75% discount** (0.25x) |
| **Telemetry Key** | `usage.prompt_tokens_details.cached_tokens` | `usage.cache_read_input_tokens`, `usage.cache_creation_input_tokens` | `usage_metadata.cached_content_token_count` |

---

## 4. Asynchronous Batch APIs

| Dimension | OpenAI | Anthropic | Google Gemini |
| :--- | :--- | :--- | :--- |
| **Discount** | Flat **50% discount** on input & output | Flat **50% discount** on input & output | Flat **50% discount** |
| **Turnaround SLA** | 24 hours | 24 hours (most finish in <1 hour) | Asynchronous execution |
| **Input Format** | Uploaded `.jsonl` file to Files API | In-memory list or `.jsonl` requests via Batches API | Batch prediction job via Cloud Storage or SDK |
| **Polling Mechanism** | `client.batches.retrieve(batch_id)` | `client.messages.batches.retrieve(batch_id)` | Job status polling via SDK / Operation |
| **Cancellation** | `client.batches.cancel(batch_id)` | `client.messages.batches.cancel(batch_id)` | Job cancel |

---

## 5. Rate Limits & Headers

| Provider | TPM / RPM Limits | Key HTTP Response Headers |
| :--- | :--- | :--- |
| **OpenAI** | Tiered 1–5 based on payment history | `x-ratelimit-limit-requests`, `x-ratelimit-remaining-requests`, `x-ratelimit-reset-requests`, `x-ratelimit-limit-tokens`, `x-ratelimit-remaining-tokens`, `x-ratelimit-reset-tokens` |
| **Anthropic** | Tiered 1–4 based on deposit balance | `anthropic-ratelimit-requests-limit`, `anthropic-ratelimit-requests-remaining`, `anthropic-ratelimit-requests-reset`, `anthropic-ratelimit-tokens-limit`, `anthropic-ratelimit-tokens-remaining`, `retry-after` |
| **Google Gemini** | Project quota in Google Cloud Console / AI Studio | Standard Cloud Quota headers, `retry-after` on 429 |

