"""Module 6 (LangChain Suite): Enterprise Gateway Orchestrator.

Demonstrates connecting LangChain pipelines through LLM Gateways:
1. Routing LangChain ChatOpenAI through OpenRouter (https://openrouter.ai/api/v1)
2. Routing LangChain ChatOpenAI through LiteLLM Proxy (http://localhost:4000/v1)
3. Enforcing Pydantic Structured Outputs across gateway endpoints
4. Dual Telemetry: LangSmith span tracing + Audit Cost Accounting
"""

from __future__ import annotations

import os
from typing import Dict, Any
from pydantic import BaseModel, Field
from rich.console import Console
from rich.panel import Panel

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from src.langchain_suite.core.telemetry import AuditTelemetryCallbackHandler

console = Console()


class SubscriberDiagnostic(BaseModel):
    """Pydantic model for structured subscriber telemetry."""
    subscriber_id: str = Field(description="Unique customer subscriber ID (e.g. SUB-49-170...)")
    plan_tier: str = Field(description="Subscription tier: PREPAID, POSTPAID_BASIC, ENTERPRISE_5G")
    sim_status: str = Field(description="ACTIVE, SUSPENDED, PENDING_PROVISION")
    recommended_action: str = Field(description="Action to restore service")


def get_gateway_chat_model(target: str = "openrouter", model_name: str = "anthropic/claude-3.5-haiku") -> ChatOpenAI:
    """Configures a ChatOpenAI instance pointing to a gateway endpoint."""
    if target == "openrouter":
        api_key = os.getenv("OPENROUTER_API_KEY", "mock-openrouter-key")
        return ChatOpenAI(
            model=model_name,
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
            default_headers={
                "HTTP-Referer": "https://telekom.com",
                "X-Title": "Telecom AI Gateway Suite",
            },
            temperature=0.0,
        )
    elif target == "litellm_proxy":
        api_key = os.getenv("LITELLM_VIRTUAL_KEY", "sk-virtual-telekom-billing")
        base_url = os.getenv("LITELLM_PROXY_URL", "http://localhost:4000/v1")
        return ChatOpenAI(
            model=model_name,
            base_url=base_url,
            api_key=api_key,
            temperature=0.0,
        )
    else:
        raise ValueError(f"Unknown gateway target: {target}")


def run_gateway_orchestration_demo(simulate: bool = False):
    console.print("\n[bold cyan]=== Module 6: LangChain Gateway Orchestration ===[/bold cyan]\n")

    prompt = "Subscriber SUB-49-170-9821 on ENTERPRISE_5G has had SIM blocked due to roaming data ceiling threshold."

    has_openrouter = bool(os.getenv("OPENROUTER_API_KEY"))

    if simulate or not has_openrouter:
        console.print("[yellow]Running simulated structured extraction (gateway demo):[/yellow]")
        simulated_diag = SubscriberDiagnostic(
            subscriber_id="SUB-49-170-9821",
            plan_tier="ENTERPRISE_5G",
            sim_status="SUSPENDED",
            recommended_action="Execute automated spend-limit reset after corporate admin authorization.",
        )
        console.print(Panel(
            f"[bold]Subscriber ID:[/bold] {simulated_diag.subscriber_id}\n"
            f"[bold]Plan Tier:[/bold] {simulated_diag.plan_tier}\n"
            f"[bold]SIM Status:[/bold] [bold red]{simulated_diag.sim_status}[/bold red]\n"
            f"[bold]Recommended Action:[/bold] {simulated_diag.recommended_action}",
            title="LangChain Structured Output via Gateway",
            border_style="cyan",
        ))
        return

    # Live Gateway Pipeline
    try:
        model = get_gateway_chat_model(target="openrouter", model_name="anthropic/claude-3.5-haiku")
        structured_llm = model.with_structured_output(SubscriberDiagnostic)

        telemetry = AuditTelemetryCallbackHandler(verbose=False)
        diagnostic = structured_llm.invoke(
            [
                SystemMessage(content="You are a telecom core network support agent. Extract diagnostics."),
                HumanMessage(content=prompt),
            ],
            config={"callbacks": [telemetry]},
        )

        console.print(Panel(
            f"[bold]Subscriber ID:[/bold] {diagnostic.subscriber_id}\n"
            f"[bold]Plan Tier:[/bold] {diagnostic.plan_tier}\n"
            f"[bold]SIM Status:[/bold] {diagnostic.sim_status}\n"
            f"[bold]Action:[/bold] {diagnostic.recommended_action}\n\n"
            f"[green]Telemetry Summary:[/green] {telemetry.summary()}",
            title="Live LangChain via OpenRouter Gateway",
            border_style="green",
        ))
    except Exception as e:
        console.print(f"[yellow]Live gateway call unvailable ({e}). Falling back to simulation.[/yellow]")
        simulated_diag = SubscriberDiagnostic(
            subscriber_id="SUB-49-170-9821",
            plan_tier="ENTERPRISE_5G",
            sim_status="SUSPENDED",
            recommended_action="Execute automated spend-limit reset after corporate admin authorization.",
        )
        console.print(Panel(
            f"[bold]Subscriber ID:[/bold] {simulated_diag.subscriber_id}\n"
            f"[bold]Plan Tier:[/bold] {simulated_diag.plan_tier}\n"
            f"[bold]SIM Status:[/bold] [bold red]{simulated_diag.sim_status}[/bold red]\n"
            f"[bold]Recommended Action:[/bold] {simulated_diag.recommended_action}",
            title="LangChain Structured Output via Gateway (Fallback)",
            border_style="cyan",
        ))


if __name__ == "__main__":
    run_gateway_orchestration_demo()
