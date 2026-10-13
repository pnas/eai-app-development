"""Module 4: OpenAI Flex Processing Demo.

Demonstrates Flex Processing (`service_tier="flex"`) for synchronous, low-priority
batch and background workloads with a flat 50% discount on all token costs.

Official References:
- Flex Processing: https://developers.openai.com/api/docs/guides/flex-processing
- Batch API: https://developers.openai.com/api/docs/guides/batch
- Latency Optimization: https://developers.openai.com/api/docs/guides/latency-optimization
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

import openai
from src.m01_paradigms.client_factory import get_openai_client

console = Console()


def run_flex_processing_request(
    prompt: str,
    model: str = "gpt-4.1-mini",
    timeout_seconds: float = 900.0,
    use_mock_fallback: bool = True,
) -> Dict[str, Any]:
    """Execute a request using service_tier='flex' for 50% discounted synchronous compute."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key.startswith("mock") or api_key.startswith("sk-placeholder"):
        if use_mock_fallback:
            console.print("[yellow][Simulated Offline Mode] Executing synthetic Flex tier request...[/yellow]")
            return {
                "id": "chatcmpl_mock_flex_12345",
                "model": model,
                "service_tier": "flex",
                "latency_sec": 3.82,
                "input_tokens": 512,
                "output_tokens": 128,
                "standard_cost": 0.000154,
                "flex_cost": 0.000077,
                "discount_percentage": 50.0,
                "content": "Root Cause Analysis: BGP flapping was triggered by optical interface CRC degradation on core router PE-04.",
            }
        raise ValueError("Missing or mock OPENAI_API_KEY.")

    client = get_openai_client()

    t0 = time.perf_counter()
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a telecom root cause analysis engine."},
            {"role": "user", "content": prompt},
        ],
        service_tier="flex",
        timeout=timeout_seconds,
    )
    latency = time.perf_counter() - t0

    usage = response.usage
    input_tok = usage.prompt_tokens if usage else 0
    output_tok = usage.completion_tokens if usage else 0

    # Pricing reference: gpt-4.1-mini standard: $0.15 / 1M in, $0.60 / 1M out
    # Flex gives 50% discount
    std_cost = (input_tok * 0.15 + output_tok * 0.60) / 1_000_000
    flex_cost = std_cost * 0.50

    return {
        "id": response.id,
        "model": response.model,
        "service_tier": getattr(response, "service_tier", "flex"),
        "latency_sec": round(latency, 2),
        "input_tokens": input_tok,
        "output_tokens": output_tok,
        "standard_cost": round(std_cost, 6),
        "flex_cost": round(flex_cost, 6),
        "discount_percentage": 50.0,
        "content": response.choices[0].message.content or "",
    }


def compare_batch_vs_flex():
    """Display an architectural and economic comparison between Batch API and Flex Processing."""
    table = Table(title="OpenAI Asynchronous Batch API vs. Synchronous Flex Processing")
    table.add_column("Dimension", style="bold")
    table.add_column("OpenAI Batch API", style="yellow")
    table.add_column("OpenAI Flex Processing", style="green")

    table.add_row("Invocation Model", "Asynchronous (.jsonl file upload + polling)", "Synchronous (standard REST / SSE stream)")
    table.add_row("Turnaround SLA", "Within 24 hours", "Immediate (typically seconds to a few minutes)")
    table.add_row("Cost Discount", "50% off all standard token rates", "50% off all standard token rates")
    table.add_row("API Parameter", "Endpoint: `/v1/batches`", "Parameter: `service_tier='flex'`")
    table.add_row("Supported Endpoints", "`/v1/chat/completions`, `/v1/responses`, `/v1/embeddings`", "Responses API & Chat Completions API")
    table.add_row("Recommended Timeout", "N/A (Job polled asynchronously)", "15 minutes (900 seconds)")
    table.add_row("Ideal Use Case", "Nightly 100K+ document embedding or offline audits", "Background tasks, ETL pipelines, non-urgent summaries")

    console.print(table)


def main():
    console.print(Panel.fit(
        "[bold cyan]OpenAI Flex Processing Architecture[/bold cyan]\n"
        "Achieves 50% token discounts synchronously without the 24h queue delay of Batch API.",
        border_style="cyan"
    ))

    result = run_flex_processing_request(
        prompt="Analyze telemetry logs for 10 consecutive connection timeouts on edge gateway GW-09.",
        use_mock_fallback=True,
    )

    console.print(f"[bold]Response ID:[/bold] {result['id']}")
    console.print(f"[bold]Service Tier:[/bold] [green]{result['service_tier']}[/green]")
    console.print(f"[bold]Latency:[/bold] {result['latency_sec']}s")
    console.print(f"[bold]Tokens:[/bold] Input={result['input_tokens']}, Output={result['output_tokens']}")
    console.print(f"[bold]Standard Cost:[/bold] ${result['standard_cost']:.6f} | [bold green]Flex Cost (50% off):[/bold green] ${result['flex_cost']:.6f}")
    console.print(f"[bold]Summary Analysis:[/bold] {result['content']}\n")

    compare_batch_vs_flex()


if __name__ == "__main__":
    main()
