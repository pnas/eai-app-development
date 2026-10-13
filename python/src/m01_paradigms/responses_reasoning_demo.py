"""Module 1: OpenAI Responses API & Reasoning Models Demo.

Demonstrates the Responses API (`client.responses.create`) with reasoning models
(gpt-6.1-sol, gpt-6-astra), reasoning effort controls, commentary streaming,
fast mode (`service_tier="fast"`), and explicit caching options.

Official References:
- Latency Optimization: https://developers.openai.com/api/docs/guides/latency-optimization
- Fast Mode: https://developers.openai.com/api/docs/guides/fast-mode
- Prompt Caching: https://developers.openai.com/api/docs/guides/prompt-caching
- Rate Limits: https://developers.openai.com/api/docs/guides/rate-limits
- Flex Processing: https://developers.openai.com/api/docs/guides/flex-processing
"""

from __future__ import annotations

import os
import sys
import time
from typing import Any, Dict, Optional
from rich.console import Console
from rich.panel import Panel

import openai
from src.m01_paradigms.client_factory import get_openai_client

console = Console()


def run_reasoning_response(
    prompt: str,
    instructions: str = "You are a telecom network optimization architect.",
    model: str = "gpt-6.1-sol",
    effort: str = "high",
    service_tier: str = "default",
    use_mock_fallback: bool = True,
) -> Dict[str, Any]:
    """Execute a structured reasoning request via OpenAI Responses API."""
    console.print(f"\n[bold cyan]=== OpenAI Responses API: {model} (service_tier={service_tier}, effort={effort}) ===[/bold cyan]")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key.startswith("mock") or api_key.startswith("sk-placeholder"):
        if use_mock_fallback:
            console.print("[yellow][Simulated Offline Mode] Returning synthetic reasoning and answer response...[/yellow]")
            return {
                "id": "resp_mock_61sol_987654",
                "model": model,
                "service_tier": service_tier,
                "reasoning_effort": effort,
                "reasoning_summary": f"Evaluated 5G core slicing latency constraints. Analyzed jitter buffer and URLLC QoS parameters under {effort} effort.",
                "output_text": "Optimal configuration: Allocate dedicated network slice ID 0x01 with 15kHz subcarrier spacing and enable pre-emptive dynamic BWP switching.",
                "usage": {
                    "input_tokens": 1420,
                    "output_tokens": 380,
                    "reasoning_tokens": 260,
                    "cached_tokens": 1024,
                },
            }
        raise ValueError("Missing or mock OPENAI_API_KEY environment variable.")

    client = get_openai_client()

    response = client.responses.create(
        model=model,
        instructions=instructions,
        input=prompt,
        reasoning={"effort": effort, "summary": "auto"},
        service_tier=service_tier,
        prompt_cache_options={"mode": "explicit"},
    )

    # Extract output text and reasoning summaries
    output_text = ""
    reasoning_summary = ""
    if hasattr(response, "output") and response.output:
        for item in response.output:
            if getattr(item, "type", "") == "message":
                for content_part in getattr(item, "content", []):
                    if getattr(content_part, "type", "") == "text":
                        output_text += getattr(content_part, "text", "")
            elif getattr(item, "type", "") == "reasoning":
                reasoning_summary += getattr(item, "summary", "")

    usage = getattr(response, "usage", None)
    return {
        "id": getattr(response, "id", ""),
        "model": getattr(response, "model", model),
        "service_tier": service_tier,
        "reasoning_effort": effort,
        "reasoning_summary": reasoning_summary,
        "output_text": output_text,
        "usage": {
            "input_tokens": getattr(usage, "input_tokens", 0) if usage else 0,
            "output_tokens": getattr(usage, "output_tokens", 0) if usage else 0,
            "reasoning_tokens": getattr(getattr(usage, "output_tokens_details", None), "reasoning_tokens", 0) if usage else 0,
            "cached_tokens": getattr(getattr(usage, "input_tokens_details", None), "cached_tokens", 0) if usage else 0,
        },
    }


def stream_reasoning_response(
    prompt: str,
    instructions: str = "Analyze telecommunications routing policies.",
    model: str = "gpt-6.1-sol",
    use_mock_fallback: bool = True,
):
    """Stream response from OpenAI Responses API capturing reasoning vs answer phases."""
    console.print(f"\n[bold green]=== Streaming Responses API ({model}) ===[/bold green]")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key.startswith("mock") or api_key.startswith("sk-placeholder"):
        if use_mock_fallback:
            console.print("[yellow][Simulated Streaming][/yellow]")
            console.print("[dim italic][Reasoning Phase] Analyzing routing graph and BGP route-reflector topologies...[/dim italic]")
            time.sleep(0.05)
            console.print("[bold]Answer:[/bold] Apply AS-Path prepending and Local Preference 200 on primary transit links to steer outbound traffic.")
            return
        raise ValueError("Missing or mock OPENAI_API_KEY.")

    client = get_openai_client()
    stream = client.responses.create(
        model=model,
        instructions=instructions,
        input=prompt,
        reasoning={"effort": "high", "summary": "auto"},
        stream=True,
    )

    console.print("[bold]Streaming event stream:[/bold]")
    for event in stream:
        event_type = getattr(event, "type", "")
        if "reasoning" in event_type:
            delta = getattr(event, "delta", "")
            sys.stdout.write(f"[italic dim]{delta}[/italic dim]")
            sys.stdout.flush()
        elif "output" in event_type or "text" in event_type:
            delta = getattr(event, "delta", "")
            if isinstance(delta, str):
                sys.stdout.write(delta)
            elif hasattr(delta, "text"):
                sys.stdout.write(delta.text)
            sys.stdout.flush()
    print()


def main():
    console.print(Panel.fit(
        "[bold cyan]OpenAI Responses API & Reasoning Architecture[/bold cyan]\n"
        "Highlights gpt-6.1-sol & gpt-6-astra with dual-phase reasoning streaming,\n"
        "service_tier controls (fast vs flex), and explicit prompt cache options.",
        border_style="cyan"
    ))

    result = run_reasoning_response(
        prompt="Design a failover routing policy between Frankfurt and Munich 5G data centers.",
        effort="high",
        service_tier="fast",
        use_mock_fallback=True,
    )
    console.print(f"[bold]Reasoning Summary:[/bold] {result.get('reasoning_summary')}")
    console.print(f"[bold]Output Answer:[/bold] {result.get('output_text')}")
    console.print(f"[dim]Tokens: {result.get('usage')}[/dim]")

    stream_reasoning_response(
        prompt="Explain latency implications of explicit prompt cache breakpoints.",
        use_mock_fallback=True,
    )


if __name__ == "__main__":
    main()
