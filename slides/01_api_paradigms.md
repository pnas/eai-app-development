---
marp: true
theme: default
paginate: true
header: "Advanced GenAI Integration | Module 1"
footer: "Enterprise AI Engineering Course"
---

# Module 1: The Modern GenAI API Landscape
## Wire Protocols, SDK Architecture & Mental Models

**OpenAI • Anthropic • Google Gemini**

---

# 1. The Fundamental Mental Model

Building production systems with GenAI APIs is **not** simple REST CRUD:

- **Autoregressive Generation**: Payloads are processed as token streams, not static HTTP responses.
- **Divergent Wire Formats**: No single standard exists between OpenAI, Anthropic, and Google.
- **Stateless by Design**: State, conversation history, tool definitions, and system prompts must be serialized on every round-trip.
- **Probabilistic Compute vs Deterministic SLAs**: Network latency is tied to token count, not network bandwidth.

---

# 2. Message Structures Compared

```
OPENAI                        ANTHROPIC                    GOOGLE GEMINI
┌───────────────────────┐     ┌───────────────────────┐    ┌───────────────────────┐
│ system / developer    │     │ system (top-level)    │    │ system_instruction    │
├───────────────────────┤     ├───────────────────────┤    ├───────────────────────┤
│ user                  │     │ user [content blocks] │    │ user [parts]          │
├───────────────────────┤     ├───────────────────────┤    ├───────────────────────┤
│ assistant             │     │ assistant             │    │ model [parts]         │
├───────────────────────┤     └───────────────────────┘    └───────────────────────┘
│ tool (response)       │
└───────────────────────┘
```

- **OpenAI**: Messages array contains all roles (`developer`, `user`, `assistant`, `tool`).
- **Anthropic**: System prompt is a separate parameter; messages only contain `user` and `assistant`.
- **Google Gemini**: Uses `user` and `model` roles; messages contain polymorphic `parts`.

---

# 3. Content Blocks: Text, Vision & Tools

Anthropic and Google enforce explicit **typed content blocks**:

```json
// Anthropic Content Block Polymorphism
{
  "role": "user",
  "content": [
    { "type": "text", "text": "Analyze this error diagram:" },
    { "type": "image", "source": { "type": "base64", "media_type": "image/png", "data": "..." } }
  ]
}
```

- Enables interleaving text, documents, and multiple images inside a single user turn.
- Tool invocations and tool results are modeled as first-class content blocks.

---

# 4. Streaming Mechanics: SSE Under the Hood

All three providers rely on **Server-Sent Events (SSE)** over HTTP/1.1 or HTTP/2:

1. Client sends `stream: true`.
2. HTTP Response Header: `Content-Type: text/event-stream`.
3. Event stream format: `data: {"choices": [{"delta": {"content": "Hello"}}]}\n\n`.
4. Final chunk: Emits usage statistics (`prompt_tokens`, `completion_tokens`) and `finish_reason: "stop"`.

**Engineering Rule**: Always consume the stream to completion. Premature connection closes still bill for all tokens generated upstream up to the cancel signal.

---

# 5. Tool Calling Protocol Differences

| Dimension | OpenAI | Anthropic | Google Gemini |
| :--- | :--- | :--- | :--- |
| **Tool Declaration** | `tools: [{type: "function", function: {...}}]` | `tools: [{name: "...", input_schema: {...}}]` | `tools: [{function_declarations: [...]}]` |
| **Tool Response Role**| `role: "tool"`, `tool_call_id: "call_abc"` | `role: "user"`, `type: "tool_result"`, `tool_use_id: "..."` | `role: "user"`, `parts: [{function_response: {...}}]` |
| **Parallel Tools** | Supported via `tool_calls` array | Supported via multiple `tool_use` blocks | Supported via multiple `function_call` parts |

---

# 6. Key Takeaways for Senior Engineers

1. **Don't abstract prematurely**: Unified wrapper libraries often hide vendor-specific advantages (e.g. prompt caching headers or reasoning tokens).
2. **Inspect token accounting**: In streaming mode, ensure your client explicitly captures the usage chunk (OpenAI `stream_options: {"include_usage": true}`).
3. **Plan for schema versioning**: Vendor SDKs move rapidly; isolate provider clients behind an explicit interface layer.

