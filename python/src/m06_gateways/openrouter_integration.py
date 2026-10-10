"""Module 6: OpenRouter Integration & Managed Multi-Provider Routing.

Demonstrates querying OpenRouter with model failover chains and dynamic price-based routing.
"""

from __future__ import annotations

import os
from rich.console import Console
from rich.panel import Panel
from src.m01_paradigms.client_factory import get_openrouter_client

console = Console()


def run_openrouter_demo():
    console.print("\n[bold magenta]=== OpenRouter Multi-Provider Auto-Routing ===[/bold magenta]")

    if not os.getenv("OPENROUTER_API_KEY"):
        console.print("[yellow]OPENROUTER_API_KEY not set in .env. Showing simulated configuration.[/yellow]")
        console.print("""
OpenRouter Configuration:
  Base URL: https://openrouter.ai/api/v1
  Model: 'anthropic/claude-3.5-sonnet' (with fallback array ['openai/gpt-4o', 'google/gemini-flash-1.5'])
  Headers:
    HTTP-Referer: https://telekom.com
    X-Title: Telecom AI Pipeline
        """)
        return

    client = get_openrouter_client()

    # OpenRouter allows specifying fallback models in the 'models' parameter via extra_body
    response = client.chat.completions.create(
        model="anthropic/claude-3.5-haiku",
        messages=[{"role": "user", "content": "Explain why multi-region failover is essential for LLM gateways."}],
        extra_body={
            "models": ["anthropic/claude-3.5-haiku", "openai/gpt-4o-mini", "google/gemini-flash-1.5"],
            "route": "fallback",
        },
    )

    choice = response.choices[0]
    console.print(Panel(
        f"[bold]Selected Model:[/bold] {response.model}\n"
        f"[bold]Content:[/bold] {choice.message.content}\n"
        f"[green]Tokens:[/green] Input={response.usage.prompt_tokens}, Output={response.usage.completion_tokens}",
        title="OpenRouter Dynamic Routing Result",
        border_style="magenta",
    ))


def main():
    try:
        run_openrouter_demo()
    except Exception as e:
        console.print(f"[red]OpenRouter error: {e}[/red]")


if __name__ == "__main__":
    main()

