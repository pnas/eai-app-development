"""Module 6: LiteLLM Unified SDK & Proxy Integration.

Demonstrates calling 100+ LLMs via a single normalized interface with built-in
fallbacks, spending limits, and token cost tracking.
"""

from __future__ import annotations

import litellm
from rich.console import Console
from rich.panel import Panel

console = Console()

# Turn off noisy telemetry logging in education scripts
litellm.telemetry = False


def run_litellm_completion():
    console.print("\n[bold cyan]=== LiteLLM Unified Model Completion ===[/bold cyan]")

    prompt = "Summarize the architectural advantage of an API Gateway in 2 sentences."
    messages = [{"role": "user", "content": prompt}]

    # LiteLLM normalizes calls to Claude, GPT, and Gemini under the exact same syntax
    primary_model = "claude-3-5-haiku-20241022"
    fallbacks = ["gpt-4o-mini", "gemini/gemini-1.5-flash"]

    console.print(f"Calling primary model [magenta]{primary_model}[/magenta] with fallbacks: {fallbacks}")

    response = litellm.completion(
        model=primary_model,
        messages=messages,
        fallbacks=fallbacks,
        max_tokens=150,
        metadata={"service": "billing-gateway", "cost_center": "core-engineering"},
    )

    # Cost calculation is performed automatically by LiteLLM based on token counts!
    cost_usd = litellm.completion_cost(completion_response=response)
    content = response.choices[0].message.content

    console.print(Panel(
        f"[bold]Model Responded:[/bold] {response.model}\n"
        f"[bold]Response:[/bold] {content}\n\n"
        f"[green]Prompt Tokens:[/green] {response.usage.prompt_tokens}\n"
        f"[green]Completion Tokens:[/green] {response.usage.completion_tokens}\n"
        f"[bold green]Calculated Request Cost:[/bold green] ${cost_usd:.6f} USD",
        title="LiteLLM Response & Cost Telemetry",
        border_style="cyan"
    ))


def main():
    try:
        run_litellm_completion()
    except Exception as e:
        console.print(f"[red]LiteLLM execution error: {e}[/red]")


if __name__ == "__main__":
    main()

