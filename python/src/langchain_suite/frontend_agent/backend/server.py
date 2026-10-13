"""Decoupled FastAPI Agent Microservice with Server-Sent Events (SSE) Streaming.

Exposes:
- GET /health: Health probe and tool inventory.
- GET /tools: Registered tools metadata.
- POST /agent/chat/stream: Server-Sent Events (SSE) streaming endpoint.
"""

from __future__ import annotations

import json
from typing import AsyncIterator, Dict, List
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.langchain_suite.core.env import (
    get_configured_providers,
    load_workspace_env,
    validate_provider_key,
)
from src.langchain_suite.frontend_agent.backend.schemas import (
    ChatRequest,
    HealthResponse,
    ToolMetadata,
)
from src.langchain_suite.frontend_agent.core.agent import (
    astream_agent_lifecycle,
    create_agent,
)
from src.langchain_suite.frontend_agent.tools.registry import GLOBAL_TOOL_REGISTRY

# Ensure environment variables from python/.env or project root .env are loaded
load_workspace_env()

app = FastAPI(
    title="Decoupled LangChain Agent API",
    description="Microservice providing real-time tool-calling agent capabilities over HTTP / SSE",
    version="1.0.0",
)

# Enable CORS for web clients (Streamlit, React, Vue, Next.js)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory agent cache by (provider, model)
AGENT_CACHE: Dict[str, Any] = {}


def get_cached_agent(provider: str, model: str | None):
    validate_provider_key(provider)
    cache_key = f"{provider}:{model or 'default'}"
    if cache_key not in AGENT_CACHE:
        AGENT_CACHE[cache_key] = create_agent(provider=provider, model=model)
    return AGENT_CACHE[cache_key]


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Returns service health status, registered tools, and LLM provider key availability."""
    tool_names = [t.name for t in GLOBAL_TOOL_REGISTRY.get_all()]
    return HealthResponse(
        status="ok",
        service="agent-backend-sse",
        available_tools=tool_names,
        configured_providers=get_configured_providers(),
    )


@app.get("/tools", response_model=List[ToolMetadata])
async def list_tools() -> List[ToolMetadata]:
    """Returns detailed metadata and JSON schemas for all available tools."""
    return [ToolMetadata(**t) for t in GLOBAL_TOOL_REGISTRY.get_metadata()]


@app.post("/agent/chat/stream")
async def chat_stream(req: ChatRequest):
    """Executes the agent and streams lifecycle events over Server-Sent Events (SSE).

    Streamed events format:
        event: token | tool_start | tool_end | done | error
        data: <json_string>
    """
    # 1. Prepare message list
    langchain_messages = []
    if req.messages:
        for m in req.messages:
            if m.role == "user":
                langchain_messages.append(HumanMessage(content=m.content))
            elif m.role == "assistant":
                langchain_messages.append(AIMessage(content=m.content))
            elif m.role == "system":
                langchain_messages.append(SystemMessage(content=m.content))
    elif req.prompt:
        langchain_messages.append(HumanMessage(content=req.prompt))
    else:
        raise HTTPException(status_code=400, detail="Either 'prompt' or 'messages' must be provided.")

    try:
        agent = get_cached_agent(provider=req.provider, model=req.model)
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to initialize agent for provider '{req.provider}': {str(exc)}",
        )

    async def sse_event_generator() -> AsyncIterator[str]:
        async for event in astream_agent_lifecycle(
            agent=agent,
            messages=langchain_messages,
            thread_id=req.thread_id,
        ):
            event_name = event.get("event", "message")
            json_payload = json.dumps(event)
            # Standard SSE wire format:
            # event: <name>\n
            # data: <json>\n\n
            yield f"event: {event_name}\ndata: {json_payload}\n\n"

    return StreamingResponse(
        sse_event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.langchain_suite.frontend_agent.backend.server:app", host="0.0.0.0", port=8000, reload=True)

