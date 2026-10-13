"""State schema and event definitions for frontend agent integration."""

from __future__ import annotations

from typing import Annotated, Any, Dict, List, Literal, Optional, Sequence, Union
from pydantic import BaseModel, Field
from langchain_core.messages import BaseMessage
import operator


class AgentState(BaseModel):
    """LangGraph agent state containing append-only conversation history."""
    messages: Annotated[Sequence[BaseMessage], operator.add] = Field(default_factory=list)


# Standardized lifecycle event models emitted across both In-Process and SSE modes
class TokenEvent(BaseModel):
    event: Literal["token"] = "token"
    content: str


class ToolStartEvent(BaseModel):
    event: Literal["tool_start"] = "tool_start"
    tool: str
    input: Dict[str, Any] = Field(default_factory=dict)


class ToolEndEvent(BaseModel):
    event: Literal["tool_end"] = "tool_end"
    tool: str
    output: str


class DoneEvent(BaseModel):
    event: Literal["done"] = "done"
    status: str = "completed"
    finish_reason: Optional[str] = "stop"


class ErrorEvent(BaseModel):
    event: Literal["error"] = "error"
    error: str


AgentStreamEvent = Union[TokenEvent, ToolStartEvent, ToolEndEvent, DoneEvent, ErrorEvent]

