"""Test suite for Frontend Agent Showcase (Tools, Agent, FastAPI SSE, and Streamlit Clients)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.langchain_suite.frontend_agent.backend.server import app
from src.langchain_suite.frontend_agent.core.agent import create_agent, astream_agent_lifecycle
from src.langchain_suite.frontend_agent.frontend.client_in_process import run_in_process_stream
from src.langchain_suite.frontend_agent.frontend.client_remote_sse import RemoteSseAgentClient
from src.langchain_suite.frontend_agent.tools.default_tools import (
    get_current_time,
    get_random_quote,
)
from src.langchain_suite.frontend_agent.tools.registry import GLOBAL_TOOL_REGISTRY, ToolRegistry


def test_time_tool_valid_timezone():
    """Verify get_current_time formats properly for a valid IANA timezone."""
    res = get_current_time.invoke({"timezone": "Europe/Berlin"})
    assert "Europe/Berlin" in res
    assert "Current Time in" in res


def test_time_tool_fallback_on_invalid_timezone():
    """Verify get_current_time falls back to UTC on invalid timezone names."""
    res = get_current_time.invoke({"timezone": "NonExistent/Zone_404"})
    assert "defaulted to UTC" in res
    assert "Current Time:" in res


def test_quote_tool_categorized():
    """Verify get_random_quote returns properly formatted quote and author."""
    tech_quote = get_random_quote.invoke({"category": "technology"})
    assert "—" in tech_quote
    assert "[Technology]" in tech_quote

    general_quote = get_random_quote.invoke({"category": "general"})
    assert "—" in general_quote


def test_tool_registry_metadata():
    """Verify ToolRegistry catalogs tools and exports JSON schemas."""
    registry = ToolRegistry([get_current_time, get_random_quote])
    metadata = registry.get_metadata()

    names = {m["name"] for m in metadata}
    assert "get_current_time" in names
    assert "get_random_quote" in names

    time_meta = next(m for m in metadata if m["name"] == "get_current_time")
    assert "properties" in time_meta["args_schema"]
    assert "timezone" in time_meta["args_schema"]["properties"]


def test_in_process_streaming_agent():
    """Verify Pattern A: In-Process runner streams tool calls and token events."""
    events = list(
        run_in_process_stream(
            prompt="What time is it in Tokyo right now?",
            provider="mock",
            thread_id="test-in-proc-1",
        )
    )

    event_types = [e.get("event") for e in events]
    assert "tool_start" in event_types, f"Expected tool_start in {event_types}"
    assert "tool_end" in event_types, f"Expected tool_end in {event_types}"
    assert "token" in event_types, f"Expected token in {event_types}"
    assert "done" in event_types, f"Expected done in {event_types}"

    # Verify tool details
    tool_start = next(e for e in events if e.get("event") == "tool_start")
    assert tool_start["tool"] == "get_current_time"
    assert tool_start["input"]["timezone"] == "Asia/Tokyo"


def test_fastapi_health_endpoint():
    """Verify FastAPI GET /health endpoint."""
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "get_current_time" in data["available_tools"]


def test_fastapi_tools_endpoint():
    """Verify FastAPI GET /tools metadata endpoint."""
    client = TestClient(app)
    resp = client.get("/tools")
    assert resp.status_code == 200
    tools = resp.json()
    assert len(tools) >= 2
    tool_names = [t["name"] for t in tools]
    assert "get_current_time" in tool_names
    assert "get_random_quote" in tool_names


def test_fastapi_sse_chat_stream():
    """Verify Pattern B: POST /agent/chat/stream returns valid Server-Sent Events."""
    client = TestClient(app)
    payload = {
        "prompt": "Give me an inspirational quote about software",
        "provider": "mock",
        "thread_id": "test-sse-1",
    }

    with client.stream("POST", "/agent/chat/stream", json=payload) as resp:
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")

        raw_events = []
        for line in resp.iter_lines():
            if line.startswith("event:"):
                raw_events.append(line.replace("event:", "").strip())

        assert "tool_start" in raw_events
        assert "tool_end" in raw_events
        assert "token" in raw_events
        assert "done" in raw_events

