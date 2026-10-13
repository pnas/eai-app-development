"""Module 5 (LangChain): Resilience & Multi-Provider Fallback Cascades.

Contrasts custom try/except loops with LangChain's declarative .with_fallbacks():
1. Automatic failover when primary encounters 429 (Rate Limit), 500, or 529 (Overloaded).
2. Cascade order: Claude Haiku 5.5 -> GPT-4.1 Mini -> Gemini 3.8 Flash.
3. Observability of which provider ultimately served the request.
"""

from __future__ import annotations

import os
from typing import Optional
from rich.console import Console

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.language_models.chat_models import BaseChatModel
from src.langchain_suite.core.models import get_chat_model

console = Console()


class FaultyMockModel(BaseChatModel):
    """Simulates an upstream provider failure (e.g. HTTP 529 Overloaded or 429 Rate Limit)."""

    provider_name: str = "claude-haiku-5-5 (Faulty Primary)"

    @property
    def _llm_type(self) -> str:
        return "faulty_mock"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        raise ConnectionError("HTTP 529: Provider Overloaded. Primary cluster capacity exceeded.")

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        raise ConnectionError("HTTP 529: Provider Overloaded. Primary cluster capacity exceeded.")


class HealthyMockModel(BaseChatModel):
    """Simulates a healthy secondary/tertiary backup model when API keys are absent or in simulation mode."""

    provider_name: str = "backup-provider"

    @property
    def _llm_type(self) -> str:
        return "healthy_mock"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        content = (
            f"[Served by {self.provider_name}] SRv6 TI-LFA (Topology-Independent Loop-Free Alternate) "
            "pre-computes backup paths directly in the data plane, enabling sub-50ms local failover "
            "with zero micro-looping compared to classic IP Fast Reroute."
        )
        return ChatResult(
            generations=[
                ChatGeneration(
                    message=AIMessage(
                        content=content,
                        response_metadata={"model_name": self.provider_name},
                    )
                )
            ]
        )

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        return self._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


def demonstrate_fallback_cascade(simulate_failure: bool = True) -> None:
    """Builds and executes a resilient fallback cascade."""
    console.print("\n[bold yellow]=== Module 5: Declarative Fallback Cascade ===[/bold yellow]\n")

    # Tier 1, 2, 3: Configure primary, secondary, and tertiary
    if simulate_failure:
        console.print("[bold red]Simulating PRIMARY provider failure (HTTP 529 Overloaded)...[/bold red]")
        primary = FaultyMockModel(provider_name="claude-haiku-5-5 (Faulty Primary)")
        secondary = HealthyMockModel(provider_name="gpt-4.1-mini (Secondary Fallback)")
        tertiary = HealthyMockModel(provider_name="gemini-3.8-flash (Tertiary Fallback)")
    else:
        try:
            primary = get_chat_model("anthropic", "claude-haiku-5-5")
        except Exception:
            primary = FaultyMockModel(provider_name="claude-haiku-5-5 (Faulty Primary)")

        try:
            secondary = get_chat_model("openai", "gpt-4.1-mini")
        except Exception:
            secondary = HealthyMockModel(provider_name="gpt-4.1-mini (Secondary Fallback)")

        try:
            tertiary = get_chat_model("gemini", "gemini-3.8-flash")
        except Exception:
            tertiary = HealthyMockModel(provider_name="gemini-3.8-flash (Tertiary Fallback)")

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

