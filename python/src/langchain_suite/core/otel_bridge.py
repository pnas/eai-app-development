"""OpenTelemetry GenAI Semantic Conventions Bridge for LangChain and LangGraph.

Implements an OpenTelemetry-compliant callback handler that captures LLM, tool,
and chain executions conforming to the official OpenTelemetry GenAI Semantic Conventions:
- gen_ai.system (e.g. 'openai', 'anthropic', 'gemini')
- gen_ai.request.model
- gen_ai.response.model
- gen_ai.operation.name ('chat', 'execute_tool', 'agent_step')
- gen_ai.usage.prompt_tokens
- gen_ai.usage.completion_tokens
- gen_ai.usage.total_tokens

Emits standard OpenTelemetry Trace & Span structures exportable to any OTel Collector
or APM platform (Jaeger, Datadog, Dynatrace, Google Cloud Trace).
"""

from __future__ import annotations

import json
import os
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import BaseMessage
from langchain_core.outputs import LLMResult

from src.langchain_suite.core.structured_logger import PIIScrubber


def generate_trace_id() -> str:
    """Generate a random 128-bit trace ID formatted as a 32-character hexadecimal string."""
    return secrets.token_hex(16)


def generate_span_id() -> str:
    """Generate a random 64-bit span ID formatted as a 16-character hexadecimal string."""
    return secrets.token_hex(8)


@dataclass
class OpenTelemetrySpan:
    """Represents an OpenTelemetry-compliant GenAI Span."""

    name: str
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    start_time_ns: int = field(default_factory=time.time_ns)
    end_time_ns: Optional[int] = None
    status_code: str = "UNSET"  # "UNSET", "OK", "ERROR"
    status_message: Optional[str] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)

    def finish(self, status_code: str = "OK", error: Optional[Exception] = None) -> None:
        """Closes the span and calculates end timestamp."""
        self.end_time_ns = time.time_ns()
        self.status_code = status_code
        if error:
            self.status_code = "ERROR"
            self.status_message = str(error)
            self.events.append({
                "name": "exception",
                "time_unix_nano": self.end_time_ns,
                "attributes": {
                    "exception.type": type(error).__name__,
                    "exception.message": str(error),
                },
            })

    @property
    def duration_ms(self) -> float:
        """Returns span duration in milliseconds."""
        if not self.end_time_ns:
            return (time.time_ns() - self.start_time_ns) / 1_000_000.0
        return (self.end_time_ns - self.start_time_ns) / 1_000_000.0

    def to_dict(self) -> Dict[str, Any]:
        """Serializes span to a human-readable dictionary."""
        return {
            "name": self.name,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "start_time_iso": datetime.fromtimestamp(self.start_time_ns / 1e9, tz=timezone.utc).isoformat(),
            "end_time_iso": (
                datetime.fromtimestamp(self.end_time_ns / 1e9, tz=timezone.utc).isoformat()
                if self.end_time_ns
                else None
            ),
            "duration_ms": round(self.duration_ms, 2),
            "status": {"code": self.status_code, "message": self.status_message},
            "attributes": self.attributes,
            "events": self.events,
        }

    def to_otlp_format(self) -> Dict[str, Any]:
        """Converts to OpenTelemetry OTLP/JSON protocol span schema."""
        return {
            "traceId": self.trace_id,
            "spanId": self.span_id,
            "parentSpanId": self.parent_span_id or "",
            "name": self.name,
            "kind": 3 if "chat" in self.name or "llm" in self.name else 1,  # SPAN_KIND_CLIENT or INTERNAL
            "startTimeUnixNano": str(self.start_time_ns),
            "endTimeUnixNano": str(self.end_time_ns or time.time_ns()),
            "attributes": [
                {"key": k, "value": {"stringValue": str(v)} if isinstance(v, str) else (
                    {"intValue": str(v)} if isinstance(v, int) else {"doubleValue": float(v)}
                )}
                for k, v in self.attributes.items()
            ],
            "status": {
                "code": 1 if self.status_code == "OK" else (2 if self.status_code == "ERROR" else 0),
                "message": self.status_message or "",
            },
        }


class OpenTelemetryGenAICallbackHandler(BaseCallbackHandler):
    """Callback Handler translating LangChain/LangGraph events to OpenTelemetry GenAI spans.
    
    Adheres to OpenTelemetry GenAI Semantic Conventions:
    https://opentelemetry.io/docs/specs/semconv/gen-ai/
    """

    def __init__(
        self,
        service_name: str = "telekom-genai-service",
        trace_id: Optional[str] = None,
        thread_id: Optional[str] = None,
        user_id: Optional[str] = None,
        scrub_pii: bool = True,
        span_exporter: Optional[Callable[[OpenTelemetrySpan], None]] = None,
    ) -> None:
        super().__init__()
        self.service_name = service_name
        self.trace_id = trace_id or generate_trace_id()
        self.thread_id = thread_id
        self.user_id = user_id
        self.scrub_pii = scrub_pii
        self.span_exporter = span_exporter

        self._active_spans: Dict[str, OpenTelemetrySpan] = {}
        self._completed_spans: List[OpenTelemetrySpan] = []
        self._parent_stack: List[str] = []

    @property
    def completed_spans(self) -> List[OpenTelemetrySpan]:
        """Return all successfully finished or errored spans."""
        return self._completed_spans

    def _sanitize(self, data: Any) -> Any:
        if not self.scrub_pii:
            return data
        return PIIScrubber.scrub_data(data)

    def _current_parent_span_id(self) -> Optional[str]:
        return self._parent_stack[-1] if self._parent_stack else None

    # -------------------------------------------------------------------------
    # LLM & Chat Model Events
    # -------------------------------------------------------------------------

    def on_chat_model_start(
        self,
        serialized: Dict[str, Any],
        messages: List[List[BaseMessage]],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        model_name = (
            (metadata or {}).get("model_name")
            or (metadata or {}).get("ls_model_name")
            or (serialized or {}).get("kwargs", {}).get("model")
            or (serialized or {}).get("name", "chat_model")
        )
        system = "openai" if "gpt" in str(model_name).lower() else (
            "anthropic" if "claude" in str(model_name).lower() else (
                "gemini" if "gemini" in str(model_name).lower() else "unknown"
            )
        )

        span = OpenTelemetrySpan(
            name=f"gen_ai.chat {model_name}",
            trace_id=self.trace_id,
            span_id=generate_span_id(),
            parent_span_id=self._current_parent_span_id(),
            attributes={
                "gen_ai.system": system,
                "gen_ai.request.model": str(model_name),
                "gen_ai.operation.name": "chat",
                "service.name": self.service_name,
            },
        )
        if self.thread_id:
            span.attributes["session.id"] = self.thread_id
        if self.user_id:
            span.attributes["user.id"] = self.user_id

        # Capture prompt preview (sanitized)
        if messages and len(messages) > 0 and len(messages[0]) > 0:
            last_msg = messages[0][-1]
            content = getattr(last_msg, "content", "")
            span.attributes["gen_ai.prompt"] = self._sanitize(str(content)[:500])

        self._active_spans[str(run_id)] = span
        self._parent_stack.append(span.span_id)

    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        if str(run_id) in self._active_spans:
            return  # Handled by chat_model_start
        model_name = (serialized or {}).get("name", "llm")
        span = OpenTelemetrySpan(
            name=f"gen_ai.completion {model_name}",
            trace_id=self.trace_id,
            span_id=generate_span_id(),
            parent_span_id=self._current_parent_span_id(),
            attributes={
                "gen_ai.system": "langchain",
                "gen_ai.request.model": str(model_name),
                "gen_ai.operation.name": "completion",
                "service.name": self.service_name,
            },
        )
        if prompts:
            span.attributes["gen_ai.prompt"] = self._sanitize(prompts[0][:500])
        self._active_spans[str(run_id)] = span
        self._parent_stack.append(span.span_id)

    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        span = self._active_spans.pop(str(run_id), None)
        if not span:
            return

        # Extract standard GenAI token metrics
        usage = (response.llm_output or {}).get("token_usage", {})
        if not usage and response.generations and response.generations[0]:
            first_gen = response.generations[0][0]
            usage = getattr(first_gen, "generation_info", {}).get("usage_metadata", {})

        prompt_tokens = usage.get("prompt_tokens") or usage.get("input_tokens") or 0
        completion_tokens = usage.get("completion_tokens") or usage.get("output_tokens") or 0
        total_tokens = usage.get("total_tokens") or (prompt_tokens + completion_tokens)

        span.attributes["gen_ai.usage.prompt_tokens"] = prompt_tokens
        span.attributes["gen_ai.usage.completion_tokens"] = completion_tokens
        span.attributes["gen_ai.usage.total_tokens"] = total_tokens

        # Record completion response preview
        if response.generations and response.generations[0]:
            first_text = response.generations[0][0].text
            span.attributes["gen_ai.completion"] = self._sanitize(first_text[:500])

        span.finish(status_code="OK")
        if self._parent_stack and self._parent_stack[-1] == span.span_id:
            self._parent_stack.pop()

        self._completed_spans.append(span)
        if self.span_exporter:
            self.span_exporter(span)

    def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        span = self._active_spans.pop(str(run_id), None)
        if not span:
            return

        span.finish(status_code="ERROR", error=error if isinstance(error, Exception) else Exception(str(error)))
        if self._parent_stack and self._parent_stack[-1] == span.span_id:
            self._parent_stack.pop()

        self._completed_spans.append(span)
        if self.span_exporter:
            self.span_exporter(span)

    # -------------------------------------------------------------------------
    # Tool Execution Events
    # -------------------------------------------------------------------------

    def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        tool_name = (serialized or {}).get("name", "unknown_tool")
        span = OpenTelemetrySpan(
            name=f"gen_ai.tool {tool_name}",
            trace_id=self.trace_id,
            span_id=generate_span_id(),
            parent_span_id=self._current_parent_span_id(),
            attributes={
                "gen_ai.operation.name": "execute_tool",
                "gen_ai.tool.name": tool_name,
                "gen_ai.tool.input": str(self._sanitize(input_str))[:300],
                "service.name": self.service_name,
            },
        )
        self._active_spans[str(run_id)] = span
        self._parent_stack.append(span.span_id)

    def on_tool_end(
        self,
        output: Any,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        span = self._active_spans.pop(str(run_id), None)
        if not span:
            return

        span.attributes["gen_ai.tool.output"] = str(self._sanitize(output))[:500]
        span.finish(status_code="OK")

        if self._parent_stack and self._parent_stack[-1] == span.span_id:
            self._parent_stack.pop()

        self._completed_spans.append(span)
        if self.span_exporter:
            self.span_exporter(span)

    def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        span = self._active_spans.pop(str(run_id), None)
        if not span:
            return

        span.finish(status_code="ERROR", error=error if isinstance(error, Exception) else Exception(str(error)))
        if self._parent_stack and self._parent_stack[-1] == span.span_id:
            self._parent_stack.pop()

        self._completed_spans.append(span)
        if self.span_exporter:
            self.span_exporter(span)

    # -------------------------------------------------------------------------
    # Chain / Agent Workflow Events
    # -------------------------------------------------------------------------

    def on_chain_start(
        self,
        serialized: Dict[str, Any],
        inputs: Dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        chain_name = (serialized or {}).get("name") or (metadata or {}).get("name", "chain")
        span = OpenTelemetrySpan(
            name=f"workflow.{chain_name}",
            trace_id=self.trace_id,
            span_id=generate_span_id(),
            parent_span_id=self._current_parent_span_id(),
            attributes={
                "gen_ai.operation.name": "workflow_step",
                "workflow.name": chain_name,
                "service.name": self.service_name,
            },
        )
        self._active_spans[str(run_id)] = span
        self._parent_stack.append(span.span_id)

    def on_chain_end(
        self,
        outputs: Dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        span = self._active_spans.pop(str(run_id), None)
        if not span:
            return

        span.finish(status_code="OK")
        if self._parent_stack and self._parent_stack[-1] == span.span_id:
            self._parent_stack.pop()

        self._completed_spans.append(span)
        if self.span_exporter:
            self.span_exporter(span)

    def on_chain_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        span = self._active_spans.pop(str(run_id), None)
        if not span:
            return

        span.finish(status_code="ERROR", error=error if isinstance(error, Exception) else Exception(str(error)))
        if self._parent_stack and self._parent_stack[-1] == span.span_id:
            self._parent_stack.pop()

        self._completed_spans.append(span)
        if self.span_exporter:
            self.span_exporter(span)

    # -------------------------------------------------------------------------
    # OTLP Payload Exporter
    # -------------------------------------------------------------------------

    def export_otlp_payload(self) -> Dict[str, Any]:
        """Serializes all collected spans into a standard OpenTelemetry OTLP/HTTP Trace payload."""
        return {
            "resourceSpans": [
                {
                    "resource": {
                        "attributes": [
                            {"key": "service.name", "value": {"stringValue": self.service_name}},
                            {"key": "telemetry.sdk.language", "value": {"stringValue": "python"}},
                            {"key": "telemetry.sdk.name", "value": {"stringValue": "opentelemetry-genai-bridge"}},
                        ]
                    },
                    "scopeSpans": [
                        {
                            "scope": {"name": "langchain_suite.otel_bridge", "version": "1.0.0"},
                            "spans": [span.to_otlp_format() for span in self._completed_spans],
                        }
                    ],
                }
            ]
        }

