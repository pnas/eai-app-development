"""Enterprise Structured Logging for LangChain and LangGraph.

Provides production-ready JSON logging, PII sanitization, correlation ID
tracking (thread_id, run_id), and non-invasive callback handlers that capture
agent internals in parallel with LangSmith tracing.
"""

from __future__ import annotations

import json
import logging
import re
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult


class PIIScrubber:
    """Sanitizes sensitive data patterns (emails, tokens, phone numbers) before logging."""

    EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
    API_KEY_PATTERN = re.compile(r"(?:api[_-]?key|token|secret|password)[\"':\s=]+([a-zA-Z0-9_-]{8,})", re.IGNORECASE)
    PHONE_PATTERN = re.compile(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")

    @classmethod
    def scrub_text(cls, text: str) -> str:
        if not text:
            return text
        sanitized = cls.EMAIL_PATTERN.sub("[REDACTED_EMAIL]", text)
        sanitized = cls.PHONE_PATTERN.sub("[REDACTED_PHONE]", sanitized)
        sanitized = cls.API_KEY_PATTERN.sub(r'api_key="[REDACTED_CREDENTIAL]"', sanitized)
        return sanitized

    @classmethod
    def scrub_data(cls, data: Any) -> Any:
        """Recursively scrubs dicts, lists, and primitives while normalizing objects."""
        if hasattr(data, "content") and hasattr(data, "type"):
            # LangChain message object (HumanMessage, AIMessage, ToolMessage, etc.)
            msg_dict: Dict[str, Any] = {"type": getattr(data, "type"), "content": cls.scrub_text(str(data.content))}
            if hasattr(data, "tool_calls") and data.tool_calls:
                msg_dict["tool_calls"] = cls.scrub_data(data.tool_calls)
            return msg_dict
        elif hasattr(data, "model_dump"):
            return cls.scrub_data(data.model_dump())
        elif isinstance(data, dict):
            return {
                str(k): "[REDACTED_CREDENTIAL]" if any(s in str(k).lower() for s in ["key", "secret", "token", "password"])
                else cls.scrub_data(v)
                for k, v in data.items()
            }
        elif isinstance(data, (list, tuple, set)):
            return [cls.scrub_data(item) for item in data]
        elif isinstance(data, str):
            return cls.scrub_text(data)
        elif isinstance(data, (int, float, bool)) or data is None:
            return data
        return str(data)


def safe_json_default(obj: Any) -> Any:
    """Fallback JSON serializer for custom objects, models, and sets."""
    if hasattr(obj, "content") and hasattr(obj, "type"):
        return {"type": obj.type, "content": str(obj.content)}
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    if isinstance(obj, (set, frozenset)):
        return list(obj)
    return str(obj)


class JSONFormatter(logging.Formatter):
    """Formats log records as structured, single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Include custom structured fields if passed via extra
        if hasattr(record, "agent_event"):
            log_entry["agent_event"] = getattr(record, "agent_event")
        if hasattr(record, "correlation"):
            log_entry["correlation"] = getattr(record, "correlation")
        if hasattr(record, "telemetry"):
            log_entry["telemetry"] = getattr(record, "telemetry")
        if hasattr(record, "payload"):
            log_entry["payload"] = PIIScrubber.scrub_data(getattr(record, "payload"))

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=safe_json_default)


def get_structured_logger(name: str = "agent.telemetry", level: int = logging.INFO) -> logging.Logger:
    """Configures and returns a dedicated JSON structured logger."""
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid duplicate handlers if initialized multiple times
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        logger.propagate = False

    return logger


class StructuredLoggingCallbackHandler(BaseCallbackHandler):
    """LangChain callback handler capturing agent execution events into structured JSON logs.

    Works alongside LangSmith out-of-band tracing without interference.
    """

    def __init__(
        self,
        logger: Optional[logging.Logger] = None,
        thread_id: Optional[str] = None,
        scrub_pii: bool = True,
    ):
        super().__init__()
        self.logger = logger or get_structured_logger()
        self.thread_id = thread_id
        self.scrub_pii = scrub_pii
        self._start_times: Dict[str, float] = {}

    def _get_correlation(self, run_id: Any, parent_run_id: Optional[Any] = None) -> Dict[str, Any]:
        return {
            "run_id": str(run_id),
            "parent_run_id": str(parent_run_id) if parent_run_id else None,
            "thread_id": self.thread_id,
        }

    def on_chain_start(
        self,
        serialized: Optional[Dict[str, Any]],
        inputs: Dict[str, Any],
        *,
        run_id: Any,
        parent_run_id: Optional[Any] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Emitted when a chain or LangGraph node begins execution."""
        run_id_str = str(run_id)
        self._start_times[run_id_str] = time.perf_counter()

        metadata = metadata or {}
        serialized = serialized or {}
        node_name = metadata.get("langgraph_node") or serialized.get("name") or (serialized.get("id") or ["node"])[-1]

        if not self.thread_id and "thread_id" in metadata:
            self.thread_id = str(metadata["thread_id"])

        self.logger.info(
            f"Node '{node_name}' started",
            extra={
                "agent_event": "node.start",
                "correlation": self._get_correlation(run_id, parent_run_id),
                "telemetry": {"node_name": node_name, "tags": tags or []},
                "payload": inputs if not self.scrub_pii else PIIScrubber.scrub_data(inputs),
            },
        )

    def on_chain_end(
        self,
        outputs: Dict[str, Any],
        *,
        run_id: Any,
        parent_run_id: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        """Emitted when a chain or LangGraph node completes execution."""
        run_id_str = str(run_id)
        start_time = self._start_times.pop(run_id_str, time.perf_counter())
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        self.logger.info(
            f"Node completed in {duration_ms}ms",
            extra={
                "agent_event": "node.end",
                "correlation": self._get_correlation(run_id, parent_run_id),
                "telemetry": {"duration_ms": duration_ms},
                "payload": outputs if not self.scrub_pii else PIIScrubber.scrub_data(outputs),
            },
        )

    def on_chat_model_start(
        self,
        serialized: Optional[Dict[str, Any]],
        messages: List[List[Any]],
        *,
        run_id: Any,
        parent_run_id: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        """Emitted when a ChatModel begins processing a prompt turn."""
        run_id_str = str(run_id)
        self._start_times[run_id_str] = time.perf_counter()
        inv_params = kwargs.get("invocation_params", {})
        model_name = inv_params.get("model_name") or inv_params.get("model") or "unknown_model"

        turn_count = len(messages[0]) if messages else 0
        self.logger.info(
            f"ChatModel '{model_name}' invoked with {turn_count} messages",
            extra={
                "agent_event": "llm.start",
                "correlation": self._get_correlation(run_id, parent_run_id),
                "telemetry": {
                    "model_name": model_name,
                    "input_message_count": turn_count,
                    "temperature": inv_params.get("temperature", 0.0),
                },
            },
        )

    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: Any,
        parent_run_id: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        """Emitted when ChatModel completes and returns generations and token counts."""
        run_id_str = str(run_id)
        start_time = self._start_times.pop(run_id_str, time.perf_counter())
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0

        if response.llm_output and "token_usage" in response.llm_output:
            u = response.llm_output["token_usage"]
            prompt_tokens = u.get("prompt_tokens", 0)
            completion_tokens = u.get("completion_tokens", 0)
            total_tokens = u.get("total_tokens", prompt_tokens + completion_tokens)
        elif response.generations and response.generations[0]:
            first_gen = response.generations[0][0]
            if hasattr(first_gen, "message") and hasattr(first_gen.message, "usage_metadata"):
                meta = first_gen.message.usage_metadata or {}
                prompt_tokens = meta.get("input_tokens", 0)
                completion_tokens = meta.get("output_tokens", 0)
                total_tokens = meta.get("total_tokens", prompt_tokens + completion_tokens)

        self.logger.info(
            f"ChatModel completed in {duration_ms}ms ({total_tokens} tokens)",
            extra={
                "agent_event": "llm.end",
                "correlation": self._get_correlation(run_id, parent_run_id),
                "telemetry": {
                    "duration_ms": duration_ms,
                    "tokens": {
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "total_tokens": total_tokens,
                    },
                },
            },
        )

    def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: Any,
        parent_run_id: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        """Emitted on LLM provider failure or rate limit."""
        run_id_str = str(run_id)
        start_time = self._start_times.pop(run_id_str, time.perf_counter())
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        self.logger.error(
            f"ChatModel error: {error}",
            extra={
                "agent_event": "llm.error",
                "correlation": self._get_correlation(run_id, parent_run_id),
                "telemetry": {"duration_ms": duration_ms, "error_type": type(error).__name__},
            },
            exc_info=True,
        )

    def on_tool_start(
        self,
        serialized: Optional[Dict[str, Any]],
        input_str: str,
        *,
        run_id: Any,
        parent_run_id: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        """Emitted when agent executes a tool."""
        run_id_str = str(run_id)
        self._start_times[run_id_str] = time.perf_counter()
        serialized = serialized or {}
        tool_name = serialized.get("name") or "unknown_tool"

        sanitized_input = PIIScrubber.scrub_text(input_str) if self.scrub_pii else input_str
        self.logger.info(
            f"Tool '{tool_name}' invoked",
            extra={
                "agent_event": "tool.start",
                "correlation": self._get_correlation(run_id, parent_run_id),
                "telemetry": {"tool_name": tool_name},
                "payload": {"input": sanitized_input},
            },
        )

    def on_tool_end(
        self,
        output: str,
        *,
        run_id: Any,
        parent_run_id: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        """Emitted when tool returns result."""
        run_id_str = str(run_id)
        start_time = self._start_times.pop(run_id_str, time.perf_counter())
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        sanitized_output = PIIScrubber.scrub_text(str(output)) if self.scrub_pii else str(output)
        self.logger.info(
            f"Tool execution completed in {duration_ms}ms",
            extra={
                "agent_event": "tool.end",
                "correlation": self._get_correlation(run_id, parent_run_id),
                "telemetry": {"duration_ms": duration_ms},
                "payload": {"output": sanitized_output},
            },
        )

    def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: Any,
        parent_run_id: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        """Emitted when tool raises exception."""
        run_id_str = str(run_id)
        start_time = self._start_times.pop(run_id_str, time.perf_counter())
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        self.logger.error(
            f"Tool execution failed: {error}",
            extra={
                "agent_event": "tool.error",
                "correlation": self._get_correlation(run_id, parent_run_id),
                "telemetry": {"duration_ms": duration_ms, "error_type": type(error).__name__},
            },
            exc_info=True,
        )
