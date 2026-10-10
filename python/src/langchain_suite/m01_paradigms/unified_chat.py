"""Module 1 (LangChain): Unified Chat Models, Streaming, and Normalized Content Blocks.

Contrasts low-level SDK wire calls with LangChain's BaseChatModel abstraction:
1. Unified Message Hierarchy: SystemMessage, HumanMessage, AIMessage
2. Uniform streaming across providers via .stream()
3. Real-time telemetry via AuditTelemetryCallbackHandler
"""

from __future__ import annotations

import sys
from rich.console import Console
from rich.table import Table

from langchain_core.messages import HumanMessage, SystemMessage
from src.langchain_suite.core.models import get_chat_model
from src.langchain_suite.core.telemetry import AuditTelemetryCallbackHandler

console = Console()


def compare_unified_chat(prompt: str, system_prompt: str) -> None:
    """Invokes OpenAI, Anthropic, and Gemini through uniform LangChain interfaces."""
    providers = ["openai", "anthropic", "gemini"]
    results = []
    telemetry = AuditTelemetryCallbackHandler(verbose=False)

    console.print("\n[bold yellow]=== Module 1: Unified Chat Invocation & Streaming ===[/bold yellow]\n")

    for provider in providers:
        console.print(f"[bold cyan]Invoking {provider.upper()} with normalized messages...[/bold cyan]")
        try:
            model = get_chat_model(provider, temperature=0.1)

            # Standardized message array: no vendor-specific payload conversion needed
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=prompt),
            ]

            # Stream tokens uniformly across any provider
            chunks = []
            sys.stdout.write(f"[{provider.upper()} STREAM]: ")
            for chunk in model.stream(messages, config={"callbacks": [telemetry]}):
                text = chunk.content
                if isinstance(text, str):
                    chunks.append(text)
                    sys.stdout.write(text)
                    sys.stdout.flush()
            sys.stdout.write("\n\n")

            full_text = "".join(chunks)
            results.append({
                "provider": provider.upper(),
                "model": getattr(model, "model_name", getattr(model, "model", "default")),
                "length": len(full_text),
                "status": "SUCCESS",
            })
        except Exception as e:
            results.append({
                "provider": provider.upper(),
                "model": "N/A",
                "length": 0,
                "status": f"FAILED: {e}",
            })

    table = Table(title="Unified LangChain Provider Comparison")
    table.add_column("Provider", style="cyan")
    table.add_column("Model", style="yellow")
    table.add_column("Response Length", justify="right")
    table.add_column("Status", style="green")

    for r in results:
        table.add_row(r["provider"], str(r["model"]), str(r["length"]), r["status"])

    console.print(table)
    console.print("\n[bold]Telemetry Audit Summary:[/bold]", telemetry.summary())


if __name__ == "__main__":
    sys_prompt = "You are an enterprise telecom assistant. Be concise and technical."
    test_prompt = "Explain in 2 sentences why fiber optic lines have lower attenuation than copper coaxial cable."
    compare_unified_chat(test_prompt, sys_prompt)

