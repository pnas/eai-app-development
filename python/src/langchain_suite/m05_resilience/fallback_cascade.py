"""Module 5 (LangChain): Resilience & Multi-Provider Fallback Cascades.

Contrasts custom try/except loops with LangChain's declarative .with_fallbacks():
1. Automatic failover when primary encounters 429 (Rate Limit), 500, or 529 (Overloaded).
2. Cascade order: Claude 3.5 Haiku -> GPT-4o-mini -> Gemini 2.0 Flash.
3. Observability of which provider ultimately served the request.
"""

from __future__ import annotations

import os
from typing import Optional
from rich.console import Console

from langchain_core.messages import HumanMessage
from langchain_core.language_models.chat_models import BaseChatModel
from src.langchain_suite.core.models import get_chat_model

console = Console()


class FaultyMockModel(BaseChatModel):
    """Simulates an upstream provider failure (e.g. HTTP 529 Overloaded or 429 Rate Limit)."""

    provider_name: str = "failing-primary"

    @property
    def _llm_type(self) -> str:
        return "faulty_mock"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        raise ConnectionError("HTTP 529: Provider Overloaded. Primary cluster capacity exceeded.")

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        raise ConnectionError("HTTP 529: Provider Overloaded. Primary cluster capacity exceeded.")


def demonstrate_fallback_cascade(simulate_failure: bool = True) -> None:
    """Builds and executes a resilient fallback cascade."""
    console.print("\n[bold yellow]=== Module 5: Declarative Fallback Cascade ===[/bold yellow]\n")

    # Tier 1: Primary (or mock failing model to demonstrate failover)
    if simulate_failure:
        console.print("[bold red]Simulating PRIMARY provider failure (HTTP 529 Overloaded)...[/bold red]")
        primary = FaultyMockModel()
    else:
        primary = get_chat_model("anthropic")

    # Tier 2: Secondary fallback
    secondary = get_chat_model("openai")

    # Tier 3: Tertiary fallback
    tertiary = get_chat_model("gemini")

    # Declarative fallback cascade
    resilient_chain = primary.with_fallbacks([secondary, tertiary])

    query = "Analyze the latency implication of using SRv6 TI-LFA fast reroute."
    console.print(f"[bold cyan]Dispatching prompt:[/bold cyan] '{query}'")

    try:
        response = resilient_chain.invoke([HumanMessage(content=query)])
        console.print(f"[bold green]✅ Request Recovered Successfully![/bold green]")
        console.print(f"Content preview: {str(response.content)[:120]}...")
        if hasattr(response, "response_metadata"):
            meta = response.response_metadata
            console.print(f"Served by metadata: {meta.get('model_name') or meta.get('model', 'backup')}")
    except Exception as e:
        console.print(f"[bold red]❌ Cascade exhausted all fallbacks: {e}[/bold red]")


if __name__ == "__main__":
    demonstrate_fallback_cascade(simulate_failure=True)

