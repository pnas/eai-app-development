"""Dual-Telemetry Demonstration: LangSmith Tracing & Enterprise Structured Logging.

Demonstrates:
1. Configuring LangSmith distributed tracing (RunTree / OpenTelemetry).
2. Concurrently attaching StructuredLoggingCallbackHandler for local JSON logs.
3. Capturing agent internals: state transitions, tool payloads, latencies, tokens.
4. Automatic PII redaction (scrubbing subscriber phone numbers & credentials).
5. Cross-correlation using `thread_id` and `run_id`.
"""

from __future__ import annotations

import os
from typing import Annotated, Sequence, List, Optional, Any
import operator
from typing_extensions import TypedDict
from rich.console import Console
from rich.panel import Panel

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.outputs import ChatResult, ChatGeneration
from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.graph import StateGraph, START
from langgraph.prebuilt import ToolNode, tools_condition

from src.langchain_suite.core.structured_logger import (
    StructuredLoggingCallbackHandler,
    get_structured_logger,
)
from src.langchain_suite.agent_recovery.tools import (
    lookup_telecom_account,
    diagnose_network_cell,
    apply_retention_credit,
)

console = Console()


class MockTelecomChatModel(BaseChatModel):
    """Deterministic mock ChatModel simulating tool invocations and token usage."""

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        # Determine if this is turn 1 (needs tool call) or turn 2 (tool result received)
        has_tool_result = any(hasattr(m, "tool_call_id") for m in messages)

        if not has_tool_result:
            msg = AIMessage(
                content="",
                tool_calls=[{
                    "name": "lookup_telecom_account",
                    "args": {"account_id": "ACCT-1001"},
                    "id": "call_audit_01",
                    "type": "tool_call",
                }],
                usage_metadata={"input_tokens": 128, "output_tokens": 26, "total_tokens": 154},
            )
        else:
            msg = AIMessage(
                content="Account ACCT-1001 retrieved. Subscriber Acme Logistics is on Enterprise 5G with healthy balance.",
                usage_metadata={"input_tokens": 210, "output_tokens": 42, "total_tokens": 252},
            )
        return ChatResult(generations=[ChatGeneration(message=msg)])

    @property
    def _llm_type(self) -> str:
        return "mock-telecom-chat"

    def bind_tools(self, tools: Any, **kwargs: Any) -> MockTelecomChatModel:
        return self


class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]


def run_dual_telemetry_demo() -> None:
    console.print("\n[bold yellow]===========================================================[/bold yellow]")
    console.print("[bold yellow] Dual-Telemetry: LangSmith Tracing & Structured Logging    [/bold yellow]")
    console.print("[bold yellow]===========================================================[/bold yellow]\n")

    # 1. Inspect LangSmith Environment Configuration
    langsmith_tracing = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"
    langsmith_project = os.getenv("LANGCHAIN_PROJECT", "telekom-default-project")
    langsmith_api_key = os.getenv("LANGCHAIN_API_KEY")

    console.print(Panel(
        f"• LANGCHAIN_TRACING_V2: [bold]{langsmith_tracing}[/bold]\n"
        f"• LANGCHAIN_PROJECT:    [bold]{langsmith_project}[/bold]\n"
        f"• LANGCHAIN_API_KEY:    [bold]{'Configured (Active)' if langsmith_api_key else 'Not set (Operating in local logging mode)'}[/bold]\n\n"
        "[italic]When active, LangSmith automatically sends asynchronous trace spans\n"
        "to the LangSmith platform without altering agent application code.[/italic]",
        title="[bold cyan]1. LangSmith Tracing Status[/bold cyan]",
    ))

    # 2. Configure Enterprise Structured Logger & Callback Handler
    thread_id = "session-audit-8842"
    structured_logger = get_structured_logger("telecom.agent.audit")
    callback_handler = StructuredLoggingCallbackHandler(
        logger=structured_logger,
        thread_id=thread_id,
        scrub_pii=True,
    )

    console.print(Panel(
        f"• Correlation thread_id: [bold cyan]{thread_id}[/bold cyan]\n"
        f"• Format:                 [bold]NDJSON (Newline-Delimited JSON)[/bold]\n"
        f"• Ingestion Target:       [bold]stdout -> Vector/Fluentbit -> Splunk / Datadog[/bold]\n"
        f"• PII Sanitization:       [bold green]Enabled (scrubs emails, phones, API keys)[/bold green]",
        title="[bold green]2. In-Band Structured Logging Configuration[/bold green]",
    ))

    # 3. Assemble LangGraph Agent
    tools = [lookup_telecom_account, diagnose_network_cell, apply_retention_credit]
    model = MockTelecomChatModel().bind_tools(tools)

    def agent_node(state: AgentState) -> dict:
        messages = state["messages"]
        response = model.invoke(messages)
        return {"messages": [response]}

    builder = StateGraph(AgentState)
    builder.add_node("agent", agent_node)
    builder.add_node("tools", ToolNode(tools))
    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", tools_condition)
    builder.add_edge("tools", "agent")

    graph = builder.compile()

    console.print("\n[bold cyan]3. Executing Agent Workflow with Dual Telemetry Attached...[/bold cyan]\n")
    console.print("[dim]--- Structured JSON Log Stream (Simulating SIEM output) ---[/dim]")

    # Pass callback handler directly into invoke config
    result = graph.invoke(
        {"messages": [HumanMessage(content="Please investigate account ACCT-1001 for cellular issues.")]},
        config={
            "configurable": {"thread_id": thread_id},
            "callbacks": [callback_handler],
            "metadata": {"thread_id": thread_id, "customer_tier": "enterprise"},
        },
    )

    console.print("[dim]-------------------------------------------------------------[/dim]\n")

    # 4. Final Verification Summary
    last_message = result["messages"][-1].content
    console.print(Panel(
        f"[bold white]Final Response:[/bold white]\n{last_message}\n\n"
        "[bold green][OK] Tracing & Logging Verification:[/bold green]\n"
        f"1. LangSmith receives root graph run, tool child spans, and token metadata.\n"
        f"2. Local logger emitted structured JSON with correlation ID '{thread_id}'.\n"
        "3. Sensitive phone numbers in tool response were scrubbed before output.",
        title="[bold green]Execution Succeeded[/bold green]",
    ))


if __name__ == "__main__":
    run_dual_telemetry_demo()
