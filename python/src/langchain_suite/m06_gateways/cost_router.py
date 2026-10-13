"""Module 6 (LangChain): Dynamic Model Routing, Fallback Cascades & Unit Economics.

Demonstrates:
1. Dynamic model selection (routing simple queries to gpt-4o-mini and complex queries to gpt-4o).
2. LangChain `.with_fallbacks()` for resilient cross-model failovers.
3. Callback-driven token cost accounting using production pricing tables.
4. Structured JSON extraction for routed decisions.
"""

from __future__ import annotations

import os
from typing import Dict, List
from pydantic import BaseModel, Field
from rich.console import Console
from rich.table import Table

from langchain_core.messages import HumanMessage
from src.langchain_suite.core.models import get_chat_model
from src.langchain_suite.core.telemetry import AuditTelemetryCallbackHandler

console = Console()

# Per million tokens pricing table
PRICING_USD_PER_M = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4.1-mini": {"input": 0.20, "output": 0.80},
    "gpt-4.1": {"input": 2.00, "output": 8.00},
    "gpt-6-luna": {"input": 2.00, "output": 8.00},
    "gpt-6-astra": {"input": 3.00, "output": 12.00},
}


class RoutingDecision(BaseModel):
    query_summary: str = Field(description="One-sentence summary of the query")
    complexity_tier: str = Field(description="FAST-ECONOMY or HIGH-REASONING")
    selected_model: str = Field(description="Name of the selected model")
    reasoning: str = Field(description="Why this model was chosen")


def calculate_cost(model_name: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Computes exact query cost from token usage."""
    rates = PRICING_USD_PER_M.get(model_name, {"input": 0.50, "output": 1.50})
    cost_in = (prompt_tokens / 1_000_000.0) * rates["input"]
    cost_out = (completion_tokens / 1_000_000.0) * rates["output"]
    return cost_in + cost_out


def route_and_execute(prompt: str, simulate: bool = False) -> Dict[str, str]:
    """Dynamically routes between low-cost fast model and high-capability reasoning model with fallbacks."""
    complex_keywords = ["architecture", "optimize", "refactor", "root cause", "differential", "rfc", "distributed"]
    is_complex = any(k in prompt.lower() for k in complex_keywords) or len(prompt.split()) > 25

    chosen_model_name = "gpt-4.1" if is_complex else "gpt-4.1-mini"
    fallback_model_name = "gpt-4.1-mini" if is_complex else "gpt-4.1"

    if simulate or not os.getenv("OPENAI_API_KEY"):
        # Offline educational simulation
        sim_tokens = 65 if is_complex else 35
        cost = calculate_cost(chosen_model_name, sim_tokens - 15, 15)
        return {
            "query": prompt[:50] + "...",
            "tier": "HIGH-REASONING" if is_complex else "FAST-ECONOMY",
            "model": chosen_model_name,
            "tokens": str(sim_tokens),
            "cost_usd": f"${cost:.6f}",
            "response": f"[Simulated {chosen_model_name} response for {prompt[:30]}...]",
        }

    try:
        # Primary model with fallback cascade
        primary_model = get_chat_model("openai", model=chosen_model_name, temperature=0.0)
        backup_model = get_chat_model("openai", model=fallback_model_name, temperature=0.0)

        # Attach fallback cascade
        resilient_chain = primary_model.with_fallbacks([backup_model])

        telemetry = AuditTelemetryCallbackHandler(verbose=False)
        response = resilient_chain.invoke([HumanMessage(content=prompt)], config={"callbacks": [telemetry]})

        summary = telemetry.summary()
        cost = calculate_cost(chosen_model_name, summary["total_prompt_tokens"], summary["total_completion_tokens"])

        return {
            "query": prompt[:50] + "...",
            "tier": "HIGH-REASONING" if is_complex else "FAST-ECONOMY",
            "model": chosen_model_name,
            "tokens": f"{summary['total_tokens']}",
            "cost_usd": f"${cost:.6f}",
            "response": str(response.content)[:80] + "...",
        }
    except Exception:
        sim_tokens = 65 if is_complex else 35
        cost = calculate_cost(chosen_model_name, sim_tokens - 15, 15)
        return {
            "query": prompt[:50] + "...",
            "tier": "HIGH-REASONING" if is_complex else "FAST-ECONOMY",
            "model": chosen_model_name,
            "tokens": str(sim_tokens),
            "cost_usd": f"${cost:.6f}",
            "response": f"[Simulated {chosen_model_name} response for {prompt[:30]}...]",
        }


def demonstrate_routing(simulate: bool = False) -> None:
    queries = [
        "What is the acronym APN in mobile networking?",
        "Design a multi-region active-active BSS billing architecture handling 50k transactions/sec with zero split-brain.",
        "List the 3 primary bands used in European 5G NR.",
        "Provide an in-depth root cause analysis for optical polarization mode dispersion on 400G transponders.",
    ]

    console.print("\n[bold yellow]=== Module 6: Dynamic Gateway Routing & Cost Accounting ===[/bold yellow]\n")
    results = [route_and_execute(q, simulate=simulate) for q in queries]

    table = Table(title="Dynamic Model Routing & Unit Economics")
    table.add_column("Query", style="cyan")
    table.add_column("Tier", style="magenta")
    table.add_column("Routed Model", style="yellow")
    table.add_column("Total Tokens", justify="right")
    table.add_column("Estimated Cost", style="green", justify="right")

    for r in results:
        table.add_row(r["query"], r["tier"], r["model"], r["tokens"], r["cost_usd"])

    console.print(table)


if __name__ == "__main__":
    demonstrate_routing()
