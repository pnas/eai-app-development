"""Non-invasive Observability and Telemetry Callback Handlers.

Tracks LLM traffic, step latencies, token consumption, and tool calls
without coupling logging or metrics to core business logic.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult
from rich.console import Console

console = Console()


@dataclass
class AuditRecord:
    run_id: str
    step_type: str  # "llm", "tool", "chain"
    name: str
    duration_seconds: float
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class AuditTelemetryCallbackHandler(BaseCallbackHandler):
    """Production callback handler for non-invasive traffic and latency auditing."""

    def __init__(self, trace_name: str = "production-audit", verbose: bool = True):
        super().__init__()
        self.trace_name = trace_name
        self.verbose = verbose
        self.records: List[AuditRecord] = []
        self._start_times: Dict[str, float] = {}

    def on_chat_model_start(
        self,
        serialized: Dict[str, Any],
        messages: List[List[Any]],
        *,
        run_id: Any,
        **kwargs: Any,
    ) -> None:
        """Invoked when an LLM / ChatModel starts processing a turn."""
        run_id_str = str(run_id)
        self._start_times[run_id_str] = time.perf_counter()
        model_name = kwargs.get("invocation_params", {}).get("model_name") or kwargs.get(
            "invocation_params", {}
        ).get("model", "unknown-model")

        turns_count = len(messages[0]) if messages else 0
        if self.verbose:
            console.print(
                f"[bold cyan]🔍 [START LLM][/bold cyan] run_id={run_id_str[:8]} "
                f"model=[yellow]{model_name}[/yellow] input_turns={turns_count}"
            )

    def on_llm_end(self, response: LLMResult, *, run_id: Any, **kwargs: Any) -> None:
        """Invoked when an LLM completes generation."""
        run_id_str = str(run_id)
        start_time = self._start_times.pop(run_id_str, time.perf_counter())
        duration = time.perf_counter() - start_time

        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0

        # Extract token usage from LLMResult metadata
        if response.llm_output and "token_usage" in response.llm_output:
            usage = response.llm_output["token_usage"]
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)
            total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)
        elif response.generations and response.generations[0]:
            first_gen = response.generations[0][0]
            if hasattr(first_gen, "message") and hasattr(first_gen.message, "usage_metadata"):
                meta = first_gen.message.usage_metadata or {}
                prompt_tokens = meta.get("input_tokens", 0)
                completion_tokens = meta.get("output_tokens", 0)
                total_tokens = meta.get("total_tokens", prompt_tokens + completion_tokens)

        record = AuditRecord(
            run_id=run_id_str,
            step_type="llm",
            name="chat_completion",
            duration_seconds=duration,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )
        self.records.append(record)

        if self.verbose:
            console.print(
                f"[bold green]✅ [END LLM][/bold green] run_id={run_id_str[:8]} "
                f"latency=[magenta]{duration:.3f}s[/magenta] "
                f"tokens=[bold]{total_tokens}[/bold] (prompt={prompt_tokens}, comp={completion_tokens})"
            )

    def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        *,
        run_id: Any,
        **kwargs: Any,
    ) -> None:
        """Invoked when an agent executes a tool."""
        run_id_str = str(run_id)
        self._start_times[run_id_str] = time.perf_counter()
        tool_name = serialized.get("name", "tool")
        if self.verbose:
            console.print(
                f"[bold magenta]🛠️  [TOOL INVOKE][/bold magenta] run_id={run_id_str[:8]} "
                f"tool=[yellow]{tool_name}[/yellow] input={input_str[:70]}..."
            )

    def on_tool_end(self, output: str, *, run_id: Any, **kwargs: Any) -> None:
        """Invoked when a tool finishes execution."""
        run_id_str = str(run_id)
        start_time = self._start_times.pop(run_id_str, time.perf_counter())
        duration = time.perf_counter() - start_time

        record = AuditRecord(
            run_id=run_id_str,
            step_type="tool",
            name="tool_call",
            duration_seconds=duration,
        )
        self.records.append(record)

        if self.verbose:
            console.print(
                f"[bold blue]📥 [TOOL RESULT][/bold blue] run_id={run_id_str[:8]} "
                f"duration={duration:.3f}s output={str(output)[:70]}..."
            )

    def on_chain_error(self, error: BaseException, *, run_id: Any, **kwargs: Any) -> None:
        """Invoked when an unhandled exception triggers in a chain or node."""
        run_id_str = str(run_id)
        if self.verbose:
            console.print(
                f"[bold red]❌ [CHAIN ERROR][/bold red] run_id={run_id_str[:8]} "
                f"error={type(error).__name__}: {error}"
            )

    def summary(self) -> Dict[str, Any]:
        """Aggregate traffic and performance stats."""
        total_time = sum(r.duration_seconds for r in self.records)
        total_prompt = sum(r.prompt_tokens for r in self.records)
        total_comp = sum(r.completion_tokens for r in self.records)
        return {
            "total_steps": len(self.records),
            "total_duration_sec": round(total_time, 3),
            "total_prompt_tokens": total_prompt,
            "total_completion_tokens": total_comp,
            "total_tokens": total_prompt + total_comp,
        }

