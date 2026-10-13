"""In-Process Agent Runner for Monolithic Streamlit Integration (Pattern A).

Executes the LangChain/LangGraph agent inside the Streamlit Python process.
Uses an isolated background event loop and thread-safe queue to shield
Streamlit from asyncio event-loop conflicts.
"""

from __future__ import annotations

import asyncio
import queue
import threading
from typing import Any, Dict, Iterator, List, Optional
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.langchain_suite.frontend_agent.core.agent import (
    astream_agent_lifecycle,
    create_agent,
)

# In-process cached agent instances
_IN_PROCESS_AGENT_CACHE: Dict[str, Any] = {}


def get_local_agent(provider: str = "mock", model: Optional[str] = None) -> Any:
    """Retrieve or initialize a cached LangGraph agent in the current process."""
    key = f"{provider}:{model or 'default'}"
    if key not in _IN_PROCESS_AGENT_CACHE:
        _IN_PROCESS_AGENT_CACHE[key] = create_agent(provider=provider, model=model)
    return _IN_PROCESS_AGENT_CACHE[key]


def run_in_process_stream(
    prompt: str,
    messages: Optional[List[Dict[str, str]]] = None,
    provider: str = "mock",
    model: Optional[str] = None,
    thread_id: str = "default-local-session",
) -> Iterator[Dict[str, Any]]:
    """Executes the agent in-process and yields lifecycle events synchronously.

    Yields events:
    - {"event": "token", "content": "..."}
    - {"event": "tool_start", "tool": "...", "input": {...}}
    - {"event": "tool_end", "tool": "...", "output": "..."}
    - {"event": "done", "status": "completed"}
    - {"event": "error", "error": "..."}
    """
    # 1. Format messages
    langchain_messages = []
    if messages:
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            if role == "user":
                langchain_messages.append(HumanMessage(content=content))
            elif role == "assistant":
                langchain_messages.append(AIMessage(content=content))
            elif role == "system":
                langchain_messages.append(SystemMessage(content=content))
    elif prompt:
        langchain_messages.append(HumanMessage(content=prompt))

    # 2. Get local agent instance
    try:
        agent = get_local_agent(provider=provider, model=model)
    except Exception as exc:
        yield {"event": "error", "error": f"Failed to instantiate local agent: {str(exc)}"}
        return

    # 3. Stream using an isolated thread and thread-safe queue
    event_queue: queue.Queue = queue.Queue()
    sentinel = object()

    def async_worker():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            async def run_stream():
                async for event in astream_agent_lifecycle(
                    agent=agent,
                    messages=langchain_messages,
                    thread_id=thread_id,
                ):
                    event_queue.put(event)

            loop.run_until_complete(run_stream())
        except Exception as err:
            event_queue.put({"event": "error", "error": f"In-process execution error: {str(err)}"})
        finally:
            event_queue.put(sentinel)
            loop.close()

    worker_thread = threading.Thread(target=async_worker, daemon=True)
    worker_thread.start()

    while True:
        item = event_queue.get()
        if item is sentinel:
            break
        yield item

