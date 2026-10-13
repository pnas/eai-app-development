---
marp: true
theme: default
paginate: true
header: "Advanced GenAI Integration | Module 7"
footer: "Enterprise AI Engineering Course"
---

# Module 7: Frontend Agent Architectures
## In-Process Monoliths vs. Decoupled SSE Microservices

**Dual-Stack: Python (Streamlit + FastAPI) & TypeScript (Express SPA + Microservice)**

---

# 1. The Frontend Integration Dilemma

When engineering AI-enabled user interfaces, developers face a critical architectural fork:

- **The Monolithic Prototype (In-Process)**:
  - Run the LangChain/LangGraph agent inside the UI application process.
  - Zero network hops, single deployment, rapid prototyping.
  - *Trap:* Heavy compute, memory leaks, and script reruns threaten UI responsiveness.

- **The Distributed Microservice (Decoupled over HTTP/SSE)**:
  - Isolate the agent behind an API gateway (e.g., FastAPI).
  - Stream lifecycle events over **Server-Sent Events (SSE)** to a lightweight UI.
  - *Benefit:* Independent horizontal scaling, resilient blast radius, and multi-client reuse.

---

# 2. Pattern A: Monolithic In-Process Architecture

In Streamlit, every user interaction triggers a **complete re-execution** of the script:

```
┌─────────────────────────────────────────────────────────────┐
│                 Single Python Process                       │
│                                                             │
│  ┌───────────────────────┐       ┌───────────────────────┐  │
│  │ Streamlit UI Script   │◄─────►│ Isolated Worker Thread│  │
│  │ (st.chat_message)     │ Queue │ (Private Event Loop)  │  │
│  └───────────────────────┘       └───────────┬───────────┘  │
│                                              ▼              │
│                                  ┌───────────────────────┐  │
│                                  │ LangGraph Agent       │  │
│                                  │ + Tool Registry       │  │
│                                  └───────────┬───────────┘  │
└──────────────────────────────────────────────┼──────────────┘
                                               ▼
                                      ┌─────────────────┐
                                      │ LLM Provider    │
                                      └─────────────────┘
```

- **Asyncio Trap**: Streamlit runs on Tornado. Directly calling `asyncio.run()` causes *Event loop already running* conflicts.
- **Solution**: Spawn a dedicated worker thread with a private loop and feed a thread-safe `queue.Queue`.

---

# 3. Pattern B: Decoupled Agent Microservice

Decoupling the frontend presentation layer from the agent orchestration engine:

```
┌─────────────────────────┐               ┌─────────────────────────┐
│ Streamlit Frontend      │               │ FastAPI Agent Service   │
│ (Port 8501)             │               │ (Port 8000)             │
│                         │   HTTP POST   │                         │
│ ┌─────────────────────┐ │ ────────────► │ ┌─────────────────────┐ │
│ │ st.chat_input       │ │  /chat/stream │ │ POST /chat/stream   │ │
│ └─────────────────────┘ │               │ └──────────┬──────────┘ │
│ ┌─────────────────────┐ │ ◄──────────── │            ▼            │
│ │ RemoteSseAgentClient│ │   text/event- │ ┌─────────────────────┐ │
│ │ (httpx stream)      │ │   stream(SSE) │ │ LangGraph Agent     │ │
│ └─────────────────────┘ │               │ │ + Tool Registry     │ │
└─────────────────────────┘               │ └──────────┬──────────┘ │
                                          └────────────┼────────────┘
                                                       ▼
                                              ┌─────────────────┐
                                              │ LLM Provider    │
                                              └─────────────────┘
```

- **Resilience**: Agent crashes or provider timeouts do not take down the web server.
- **Multi-Client**: The same SSE endpoint powers Streamlit, React, Vue, mobile apps, and Slack bots.

---

# 4. Why Server-Sent Events (SSE) over WebSockets?

For GenAI agent streaming, **SSE (`text/event-stream`)** is often superior to WebSockets:

| Dimension | Server-Sent Events (SSE) | WebSockets (`ws://`) |
| :--- | :--- | :--- |
| **Directionality** | Unidirectional (Server $\to$ Client) | Full Duplex (Bidirectional) |
| **Transport** | Standard HTTP/1.1 or HTTP/2 | Custom TCP Upgrade Protocol |
| **Firewall / Proxy Friendly** | Works through corporate proxies, CDNs, & ALBs | Often blocked or terminated by strict corporate firewalls |
| **Reconnection** | Native HTTP reconnect with `Last-Event-ID` | Requires custom client heartbeat & reconnect logic |
| **Fit for GenAI** | **Optimal**: Client sends prompt once, Server streams tokens | Overkill: Unnecessary complexity for request-stream models |

---

# 5. SSE Wire Protocol & Lifecycle Events

The FastAPI backend normalizes internal LangGraph events into 5 typed SSE events:

```http
POST /agent/chat/stream HTTP/1.1
Content-Type: application/json
Accept: text/event-stream

{"prompt": "What time is it in Tokyo?", "thread_id": "session-101"}
```

```text
event: tool_start
data: {"event": "tool_start", "tool": "get_current_time", "input": {"timezone": "Asia/Tokyo"}}

event: tool_end
data: {"event": "tool_end", "tool": "get_current_time", "output": "2026-10-11 04:17:34 JST"}

event: token
data: {"event": "token", "content": "The current time in Tokyo is 4:17 AM JST."}

event: done
data: {"event": "done", "status": "completed"}
```

---

# 6. End-to-End Execution Sequence

```
User          Streamlit (:8501)         FastAPI (:8000)       LangGraph Agent       LLM Provider
 │                   │                         │                     │                   │
 ├─ Submits prompt ─►│                         │                     │                   │
 │                   ├─ POST /chat/stream ────►│                     │                   │
 │                   │  (HTTP 200 SSE open) ───┤                     │                   │
 │                   │                         ├─ astream_events() ─►│                   │
 │                   │                         │                     ├─ bind_tools() ───►│
 │                   │                         │                     │◄─ tool_call ──────┤
 │                   │◄─ event: tool_start ────┼◄─ on_tool_start ────┤                   │
 │                   │   [st.status spinner]   │                     ├─ execute_tool()   │
 │                   │◄─ event: tool_end ──────┼◄─ on_tool_end ──────┤                   │
 │                   │   [status complete ✅]   │                     │                   │
 │                   │                         │                     ├─ invoke(result) ─►│
 │                   │                         │                     │◄─ token stream ───┤
 │                   │◄─ event: token ─────────┼◄─ on_model_stream ──┤                   │
 │◄─ Render markdown ┤   (Stream token chunk)  │                     │                   │
 │                   │◄─ event: done ──────────┼◄─ on_chain_end ─────┤                   │
```

---

# 7. Extensible Tool Registry Pattern

Hardcoding tools into agents creates tight coupling. We use an **open Tool Registry**:

```python
# tools/registry.py
class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool_instance: BaseTool) -> None:
        self._tools[tool_instance.name] = tool_instance

    def get_metadata(self) -> list[dict]:
        """Exports JSON schemas for UI tool inspection and dynamic validation."""
        return [{"name": t.name, "description": t.description, 
                 "schema": t.args_schema.model_json_schema()} for t in self._tools.values()]
```

- **V1 Tools**:
  - `get_current_time(timezone: str)`: Timezone-aware date/time lookup.
  - `get_random_quote(category: str)`: Categorized inspirational quotes.
- **Pluggability**: Adding a `@tool` instantly surfaces it in the Streamlit inspector and FastAPI metadata endpoint without modifying application logic.

---

# 8. Real-time UX: Eliminating the Thinking Void

LLM agents executing tools encounter high latency (1s – 8s) before generating text:

```
[ Traditional Chat UI ]
User: "What's the weather in Tokyo?"
... (5 seconds of blank frozen UI - User thinks app crashed) ...
Assistant: "The weather is 18°C and cloudy."
```

```
[ Production Agent UI with SSE Lifecycle Events ]
User: "What's the weather in Tokyo?"
⚙️ Executing tool: get_weather (args: {'city': 'Tokyo'})...
✅ Tool get_weather completed (18°C, cloudy)
Assistant: "The current weather in Tokyo is 18°C with moderate cloud cover."
```

- Using `st.status()` mapped to `tool_start` and `tool_end` gives users **instant operational transparency**.

---

# 9. TypeScript Web Application Architecture

In production enterprise environments, agents are often integrated into full-fledged TypeScript web applications:

```
┌─────────────────────────────────────────────────────────────┐
│ Browser Client (SPA - Vanilla / React / Next.js)            │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Fetch API + ReadableStream Reader (Zero-dep SSE parser) │ │
│ │ Real-time Tool Cards (tool_start / tool_end)            │ │
│ └─────────────────────────────────────────────────────────┘ │
└──────────────┬──────────────────────────────┬───────────────┘
  Pattern A:   │ Direct SSE / API Proxy       │ Pattern B: Direct SSE
  (In-Process) │                              │ (Microservice)
               ▼                              ▼
┌──────────────────────────────┐ ┌──────────────────────────────┐
│ Express Web App (:3000)      │ │ Standalone Agent Svc (:4000) │
│ - Serves SPA Static Assets   │ │ - Express HTTP / SSE API     │
│ - In-Process LangGraph Agent │ │ - LangGraph.js Agent Graph   │
│ - Streaming SSE Proxy        │ │ - Global Tool Registry       │
└──────────────────────────────┘ └──────────────────────────────┘
```

- **Frontend (`app.js`)**: Real-time token streaming and dynamic tool execution widgets.
- **Dual Integration Modes**: Switch between local in-process and remote microservice with one dropdown toggle.

---

# 10. Node.js Concurrency: In-Process Simplicity

Comparing Python Streamlit vs. Node.js Express for **In-Process Monoliths (Pattern A)**:

```
[ Python / Streamlit ]
Tornado Event Loop ──(Conflict!)──► asyncio.run() fails
Workaround: Dedicated Worker Thread + Thread-Safe queue.Queue + Polling loop

[ TypeScript / Node.js ]
Single Event Loop ──(Native Non-Blocking)──► AsyncGenerator
Express Handler ──► streamAgentLifecycle() ──► res.write("data: ...\n\n")
```

```typescript
// webApp/server.ts (Pattern A Handler)
app.post("/api/chat/in-process", async (req, res) => {
  res.setHeader("Content-Type", "text/event-stream");
  res.setHeader("Cache-Control", "no-cache");
  res.setHeader("Connection", "keep-alive");

  const generator = streamAgentLifecycle(agent, req.body.prompt, req.body.threadId);
  for await (const event of generator) {
    if (res.writableEnded) break;
    res.write(`event: ${event.event}\ndata: ${JSON.stringify(event)}\n\n`);
  }
  res.end();
});
```

---

# 11. Consuming SSE in Browser SPAs: ReadableStream

Modern browsers natively parse Server-Sent Events via the `Fetch` and `ReadableStream` APIs:

```javascript
// public/app.js (Browser Client)
const response = await fetch("/api/chat/remote", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ prompt, threadId })
});

const reader = response.body.getReader();
const decoder = new TextDecoder("utf-8");
let buffer = "";

while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  buffer += decoder.decode(value, { stream: true });
  
  const blocks = buffer.split("\n\n");
  buffer = blocks.pop() || ""; // Retain incomplete chunk
  
  for (const block of blocks) {
    const dataLine = block.split("\n").find(l => l.startsWith("data: "));
    if (dataLine) {
      const event = JSON.parse(dataLine.replace(/^data:\s*/, ""));
      handleAgentLifecycleEvent(event); // Render tokens & tool cards
    }
  }
}
```

---

# 12. Cross-Language SSE Interoperability

Because both backends strictly follow the normalized SSE lifecycle contract, they are **100% interoperable**:

```
┌────────────────────────┐                   ┌────────────────────────┐
│ Streamlit UI (Python)  │                   │ TypeScript SPA Web App │
│ (Port 8501)            │                   │ (Port 3000)            │
└───────────┬────────────┘                   └───────────┬────────────┘
            │                                            │
            ├──────────────────────┬─────────────────────┤
            │  Standard SSE Stream │  Standard SSE Stream│
            ▼                      ▼                     ▼
┌────────────────────────┐                   ┌────────────────────────┐
│ FastAPI Agent Backend  │                   │ Express Agent Backend  │
│ (Python - Port 8000)   │                   │ (TypeScript - Port 4000│
└────────────────────────┘                   └────────────────────────┘
```

- The **TypeScript Web App** can point to either the Node.js backend (`:4000`) or the Python backend (`:8000`).
- The **Python Streamlit UI** can stream from either Python FastAPI or Node.js Express.
- Standardized events: `tool_start`, `tool_end`, `token`, `done`, `error`.

---

# 13. Architectural Trade-off Matrix

| Dimension | Pattern A: Python Streamlit | Pattern A: Node.js Express | Pattern B: Decoupled Microservice |
| :--- | :--- | :--- | :--- |
| **Execution Model** | Script reruns; Worker thread + Queue | Single event loop; Async generator | Independent process behind HTTP/SSE |
| **Concurrency** | Low (Tornado thread contention) | High (Native non-blocking I/O) | **Highest** (Horizontal autoscaling via ALB/K8s) |
| **Process Isolation** | None (Agent crash crashes UI) | None (Unhandled error kills server) | **Complete** (HTTP isolation & graceful fallback) |
| **Multi-Client** | Zero (Streamlit internal only) | Zero (In-process web routes only) | **Universal** (Web, Mobile, Slack, CLI, Microservices) |
| **State Scope** | Ephemeral or SQLite in UI process | Ephemeral or SQLite in Node process | Centralized checkpointer (Redis / PostgreSQL) |
| **Best Used For** | Rapid Python POCs & data apps | Full-stack JS prototypes & simple tools | **Enterprise production platforms** |

---

# 14. Hands-on Execution & Code Tour

### Python Implementation (`python/src/langchain_suite/frontend_agent/`):
```powershell
# Unified launcher (FastAPI :8000 + Streamlit :8501):
uv run python -m src.langchain_suite.frontend_agent.run_showcase --all

# Run automated Python test suite:
uv run pytest tests/test_frontend_agent.py
```

### TypeScript Implementation (`typescript/src/langchain_suite/frontend_agent/`):
```powershell
# Unified launcher (Agent Backend :4000 + Web App :3000):
npm run start:frontend:all

# Or run individual services:
npm run start:frontend:backend   # Express SSE Agent on :4000
npm run start:frontend:webapp    # Express SPA on :3000

# Run automated TypeScript test suite:
npm run test:frontend-agent
```


