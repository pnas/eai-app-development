"""Core LangGraph Agent Factory and Lifecycle Event Streamer.

Assembles cyclical tool-calling agents with persistence, and normalizes
LangGraph v2 execution events into unified frontend lifecycle messages:
`token`, `tool_start`, `tool_end`, `error`, `done`.
"""

from __future__ import annotations

import os
from typing import Any, AsyncIterator, Dict, List, Optional, Sequence, Union
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START, MessagesState
from langgraph.prebuilt import ToolNode, tools_condition

from src.langchain_suite.core.models import get_chat_model
from src.langchain_suite.frontend_agent.core.mock_model import MockAgentChatModel
from src.langchain_suite.frontend_agent.core.state import (
    DoneEvent,
    ErrorEvent,
    TokenEvent,
    ToolEndEvent,
    ToolStartEvent,
)
from src.langchain_suite.frontend_agent.tools.registry import GLOBAL_TOOL_REGISTRY

SYSTEM_PROMPT = """You are a helpful and polite AI assistant integrated into a dual-mode Streamlit architecture demo.
You have access to tools:
- get_current_time: Check real-time date/time across different world timezones.
- get_random_quote: Fetch inspiring quotes categorized by technology, philosophy, science, or motivation.
- list_eu_documents: Discover available official EU AI Act regulatory documents and their document IDs.
- search_eu_guidelines: Deterministically search EU AI Act guidelines and regulation text for concepts, articles, or definitions.
- read_eu_article_or_section: Retrieve the full verbatim text and page citations for a specific article or section.

For any questions regarding artificial intelligence regulation, EU policy, prohibited AI practices, high-risk systems, AI system definitions, or transparency obligations, ALWAYS use the EU AI Act retrieval tools (list_eu_documents, search_eu_guidelines, read_eu_article_or_section) to find the exact text and cite the source document name and page number.
Be concise, clear, and informative.
"""


def create_agent(
    provider: str = "mock",
    model: Optional[str] = None,
    tools: Optional[List[BaseTool]] = None,
    checkpointer: Optional[BaseCheckpointSaver] = None,
) -> Any:
    """Builds and compiles a cyclical LangGraph tool-calling agent.

    Args:
        provider: 'mock', 'openai', 'anthropic', or 'gemini'.
        model: Specific model name (e.g. 'gpt-4o-mini', 'claude-3-5-haiku-20241022').
        tools: List of tools (defaults to GLOBAL_TOOL_REGISTRY).
        checkpointer: Checkpoint saver for state recovery (defaults to MemorySaver).
    """
    active_tools = tools if tools is not None else GLOBAL_TOOL_REGISTRY.get_all()
    prov_lower = provider.strip().lower()

    if prov_lower == "mock":
        chat_model: BaseChatModel = MockAgentChatModel()
    else:
        chat_model = get_chat_model(
            provider=prov_lower,
            model=model,
            temperature=0.0,
            streaming=True,
        )

    model_with_tools = chat_model.bind_tools(active_tools)
    

    def agent_node(state: MessagesState) -> Dict[str, Any]:
        messages = list(state["messages"])
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages
        response = model_with_tools.invoke(messages)
        return {"messages": [response]}

    builder = StateGraph(MessagesState)
    builder.add_node("agent", agent_node)
    builder.add_node("tools", ToolNode(active_tools))

    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", tools_condition)
    builder.add_edge("tools", "agent")

    saver = checkpointer if checkpointer is not None else MemorySaver()
    return builder.compile(checkpointer=saver)


async def astream_agent_lifecycle(
    agent: Any,
    messages: Sequence[Union[BaseMessage, tuple[str, str]]],
    thread_id: str = "default-session",
) -> AsyncIterator[Dict[str, Any]]:
    """Yields normalized lifecycle events from the LangGraph agent execution.

    Emitted events:
    - {"event": "token", "content": "..."}
    - {"event": "tool_start", "tool": "...", "input": {...}}
    - {"event": "tool_end", "tool": "...", "output": "..."}
    - {"event": "error", "error": "..."}
    - {"event": "done", "status": "completed"}
    """
    config = {"configurable": {"thread_id": thread_id}}

    try:
        async for event in agent.astream_events(
            {"messages": messages},
            config=config,
            version="v2",
        ):
            kind = event.get("event")

            # 1. Chat model streaming token chunks
            if kind == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    if isinstance(chunk.content, str):
                        yield TokenEvent(content=chunk.content).model_dump()
                    elif isinstance(chunk.content, list):
                        # Some models emit content block parts
                        for part in chunk.content:
                            if isinstance(part, str):
                                yield TokenEvent(content=part).model_dump()
                            elif isinstance(part, dict) and "text" in part:
                                yield TokenEvent(content=part["text"]).model_dump()

            # 2. Tool invocation initiated
            elif kind == "on_tool_start":
                tool_name = event.get("name", "unknown_tool")
                tool_input = event.get("data", {}).get("input", {})
                yield ToolStartEvent(tool=tool_name, input=tool_input).model_dump()

            # 3. Tool execution completed
            elif kind == "on_tool_end":
                tool_name = event.get("name", "unknown_tool")
                tool_output = str(event.get("data", {}).get("output", ""))
                yield ToolEndEvent(tool=tool_name, output=tool_output).model_dump()

        # Final signal indicating stream completion
        yield DoneEvent().model_dump()

    except Exception as exc:
        yield ErrorEvent(error=str(exc)).model_dump()

