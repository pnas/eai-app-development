"""Pydantic schemas for the decoupled Agent microservice API."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class ChatMessageItem(BaseModel):
    """Normalized chat message structure."""
    role: Literal["user", "assistant", "system"] = "user"
    content: str


class ChatRequest(BaseModel):
    """Payload for initiating a streaming agent conversation."""
    prompt: Optional[str] = Field(None, description="Direct user prompt string")
    messages: Optional[List[ChatMessageItem]] = Field(
        None,
        description="Full conversation history to preserve conversational context",
    )
    provider: str = Field(
        default="mock",
        description="LLM provider: 'mock', 'openai', 'anthropic', or 'gemini'",
    )
    model: Optional[str] = Field(
        None,
        description="Specific model identifier, e.g. 'gpt-4o-mini'",
    )
    thread_id: str = Field(
        default="session-default",
        description="Unique thread identifier for agent session state checkpointing",
    )


class ToolMetadata(BaseModel):
    """Schema descriptor for a registered agent tool."""
    name: str
    description: str
    args_schema: Dict[str, Any] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    """Microservice health check status."""
    status: str = "ok"
    service: str = "agent-backend-sse"
    available_tools: List[str] = Field(default_factory=list)
    configured_providers: Dict[str, bool] = Field(default_factory=dict)

