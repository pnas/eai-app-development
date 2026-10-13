"""Module 3: OpenAI Prompt Caching, Diagnostics & Monitoring.

Demonstrates OpenAI's prompt caching architecture across model generations:
1. Classic Implicit Prefix Caching (GPT-4o, GPT-4o-mini, o1, o3-mini):
   - Automatic prefix matching for prompts >= 1,024 tokens.
   - 128-token increment block granularity.
   - 50% discount on cache reads; 0% write surcharge.
   - Cache retention options: "in_memory" vs "24h".
   - Routing with prompt_cache_key (~15 req/min target per key).

2. Modern GPT-5.6+ / GPT-6 Dual-Mode Caching (Responses API):
   - Explicit mode: prompt_cache_options={"mode": "explicit"}.
   - Explicit breakpoints: prompt_cache_breakpoint=True.
   - Economics: 1.25x write surcharge, 0.10x read discount (90% off; 95% off on GPT-6.1 Sol: 0.05x).
   - Prewarming: prompt_cache_options.prewarm: True.
   - Cache TTL: prompt_cache_options.ttl: "30m" (minimum 30 min rolling).
   - Multi-tenant isolation: prompt_cache_key for tenant accounting & anti-probing.

3. Prompt Cache Diagnostics & Monitoring:
   - prompt_cache_options.comparison_response_id: compares against baseline.
   - prompt_cache_diagnostics: type ("cache_hit", "cache_miss"), reason ("tools_changed",
     "input_changed", "reasoning_effort_changed", etc.), and cache_missed_tokens.
   - Weighted input token cost calculation.

Official References:
- Prompt Caching: https://developers.openai.com/api/docs/guides/prompt-caching
- Latency Optimization: https://developers.openai.com/api/docs/guides/latency-optimization
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from src.m01_paradigms.client_factory import get_openai_client

console = Console()

# Synthetic enterprise knowledge base >= 1,024 tokens
LARGE_RUNBOOK = """
# TELEKOM INFRASTRUCTURE RUNBOOK: HYPER-CONVERGED KUBERNETES DEPLOYMENTS
[Chapter 1: Network Ingress Topology]
The ingress architecture utilizes Envoy proxy instances configured with circuit breaking,
rate limiting, and mTLS verification using SPIFFE/SPIRE identity documents.
Each ingress pod handles up to 10,000 active concurrent WebSocket connections.
[Chapter 2: Storage Classes and CSI Drivers]
Persistent volumes are provisioned via Ceph CSI with triple replication across failure domains.
Snapshots must be scheduled every 4 hours with 30-day immutable retention policies.
[Chapter 3: Node Autoscaling & Eviction Policies]
Karpenter manages EC2 node lifecycle. Pod Disruption Budgets (PDB) must guarantee minAvailable: 80%
at all times during spot node termination events.
[Chapter 4: Service Mesh & Observability]
Istio ambient mesh operates without sidecars using ztunnel for mTLS and waypoint proxies for L7 policies.
Telemetry spans are sampled at 10% for nominal traffic and 100% for error traces.
""" + ("\nAll cluster metrics are ingested into Prometheus and persisted to long-term Thanos storage.\n" * 50)


def calculate_input_cost(
    input_tokens: int,
    cached_tokens: int,
    cache_write_tokens: int,
    price_per_million: float = 2.50,
    cache_read_multiplier: float = 0.50,
    cache_write_multiplier: float = 1.00,
) -> float:
    """Calculate weighted input token cost following official OpenAI monitoring formulas.

    For GPT-4o / GPT-4o-mini:
      - Read multiplier = 0.50 (50% off)
      - Write multiplier = 1.00 (standard price)
    For GPT-5.6+ / GPT-6 (e.g. gpt-6-astra, gpt-6.1-sol):
      - Read multiplier = 0.10 (90% off) or 0.05 (95% off on gpt-6.1-sol)
      - Write multiplier = 1.25 (25% surcharge)
    """
    ordinary_input_tokens = input_tokens - cached_tokens - cache_write_tokens
    weighted_input_tokens = (
        ordinary_input_tokens
        + (cached_tokens * cache_read_multiplier)
        + (cache_write_tokens * cache_write_multiplier)
    )
    return (weighted_input_tokens * price_per_million) / 1_000_000


def demo_openai_prefix_caching():
    """Demonstrate automatic prefix prompt caching on GPT-4o-mini."""
    console.print(
        Panel(
            "[bold cyan]OpenAI Prompt Caching & Diagnostics Architecture[/bold cyan]\n\n"
            "• [bold]Classic Models (GPT-4o, GPT-4o-mini, o1)[/bold]:\n"
            "  - Automatic prefix matching >= 1,024 tokens in [yellow]128-token increments[/yellow].\n"
            "  - 50% read discount (0.50x), 0% write surcharge.\n"
            "  - Retention: [green]'in_memory'[/green] (5-10m) or [green]'24h'[/green] extended retention.\n"
            "  - Routing: [yellow]prompt_cache_key[/yellow] routes related traffic (~15 req/min per key).\n\n"
            "• [bold]Modern Models (GPT-5.6+, GPT-6, GPT-6.1 Sol)[/bold]:\n"
            "  - Dual-mode: [green]explicit[/green] (prompt_cache_breakpoint) vs [green]implicit[/green].\n"
            "  - Economics: 1.25x write surcharge, 0.10x read (90% discount; 95% on GPT-6.1 Sol).\n"
            "  - Prewarming: [yellow]prompt_cache_options.prewarm: True[/yellow] for zero-latency TTFT.\n"
            "  - Diagnostics: [magenta]prompt_cache_options.comparison_response_id[/magenta] explains misses.",
            title="OpenAI Cache Architecture & Diagnostics",
            border_style="cyan",
        )
    )

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key.startswith("mock") or api_key.startswith("sk-placeholder"):
        console.print("[yellow][Simulated Offline Demonstration] Displaying prefix caching metrics...[/yellow]")
        simulated_table = Table(title="OpenAI Automatic Prefix Caching (Simulated)")
        simulated_table.add_column("Call", style="cyan")
        simulated_table.add_column("Query", style="white")
        simulated_table.add_column("Total Prompt Tok", justify="right")
        simulated_table.add_column("Cached Tok (Hit)", justify="right", style="bold green")
        simulated_table.add_column("Uncached Tok (Miss)", justify="right", style="yellow")
        simulated_table.add_column("Estimated Cost ($)", justify="right", style="bold green")
        simulated_table.add_column("Latency (s)", justify="right", style="magenta")

        simulated_table.add_row("Call #1", "What is the required minAvailable...", "1420", "0", "1420", "$0.000213", "1.24s")
        simulated_table.add_row("Call #2", "What CSI driver is used for persi...", "1428", "1420", "8", "$0.000108", "0.31s")
        simulated_table.add_row("Call #3", "What is the sampling rate for nom...", "1435", "1420", "15", "$0.000109", "0.29s")
        console.print(simulated_table)
        return

    client = get_openai_client()
    model = "gpt-4o-mini"
    table = Table(title="OpenAI Automatic Prefix Caching Execution Log")
    table.add_column("Call", style="cyan")
    table.add_column("Query", style="white")
    table.add_column("Total Prompt Tok", justify="right")
    table.add_column("Cached Tok (Hit)", justify="right", style="bold green")
    table.add_column("Uncached Tok (Miss)", justify="right", style="yellow")
    table.add_column("Estimated Cost ($)", justify="right", style="bold green")
    table.add_column("Latency (s)", justify="right", style="magenta")

    queries = [
        "What is the required minAvailable percentage in Pod Disruption Budgets?",
        "What CSI driver is used for persistent volumes and how often are snapshots taken?",
        "What is the sampling rate for nominal vs error traces in the Istio ambient mesh?",
    ]

    for idx, query in enumerate(queries, start=1):
        messages = [
            {"role": "system", "content": f"You are a Telekom SRE runbook assistant.\n\n{LARGE_RUNBOOK}"},
            {"role": "user", "content": query},
        ]

        start = time.perf_counter()
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=150,
            temperature=0.0,
        )
        elapsed = time.perf_counter() - start

        usage = response.usage
        cached_tok = 0
        if usage and hasattr(usage, "prompt_tokens_details") and usage.prompt_tokens_details:
            cached_tok = getattr(usage.prompt_tokens_details, "cached_tokens", 0) or 0

        prompt_tok = usage.prompt_tokens if usage else 0
        uncached_tok = prompt_tok - cached_tok

        cost = calculate_input_cost(
            input_tokens=prompt_tok,
            cached_tokens=cached_tok,
            cache_write_tokens=0,
            price_per_million=0.15,
            cache_read_multiplier=0.50,
            cache_write_multiplier=1.00,
        )

        table.add_row(
            f"Call #{idx}",
            query[:35] + "...",
            str(prompt_tok),
            str(cached_tok),
            str(uncached_tok),
            f"${cost:.6f}",
            f"{elapsed:.2f}s",
        )

    console.print(table)


def demo_openai_explicit_caching():
    """Demonstrate modern Responses API explicit cache breakpoints and GPT-6.1 Sol pricing."""
    console.print(
        Panel(
            "[bold green]Modern Responses API Explicit Caching (GPT-6.1 Sol / GPT-6 Astra)[/bold green]\n\n"
            "• [bold]Explicit Breakpoints[/bold]: Developer controls exact cache boundary via `prompt_cache_breakpoint`.\n"
            "• [bold]Pricing Economics[/bold]:\n"
            "  - Initial Write: 1.25x surcharge on prompt write.\n"
            "  - Subsequent Reads: 0.10x (90% off) on standard GPT-6, 0.05x (95% off) on GPT-6.1 Sol!\n"
            "• [bold]Prewarming[/bold]: `prompt_cache_options: {'prewarm': True}` eliminates TTFT penalty on first user query.",
            title="Responses API Explicit Breakpoint Accounting",
            border_style="green",
        )
    )

    table = Table(title="Prompt Cache Economic Breakdown (Base $2.50 / 1M tokens, 10,000 prompt tokens)")
    table.add_column("Architecture", style="bold")
    table.add_column("Initial Write Cost", justify="right")
    table.add_column("Subsequent Hit Cost", justify="right", style="green")
    table.add_column("10-Turn Session Cost", justify="right", style="bold green")
    table.add_column("Net Savings", justify="right", style="bold cyan")

    # Uncached: 10 * 10000 * 2.50 / 1e6 = $0.25
    uncached_10 = 10 * (10000 * 2.50 / 1_000_000)
    
    # Classic (GPT-4o style): Write = 1.0x, Read = 0.50x
    c_write_classic = (10000 * 1.0 * 2.50) / 1_000_000
    c_read_classic = (10000 * 0.50 * 2.50) / 1_000_000
    classic_10 = c_write_classic + 9 * c_read_classic
    
    # Modern GPT-6: Write = 1.25x, Read = 0.10x
    c_write_gpt6 = (10000 * 1.25 * 2.50) / 1_000_000
    c_read_gpt6 = (10000 * 0.10 * 2.50) / 1_000_000
    gpt6_10 = c_write_gpt6 + 9 * c_read_gpt6

    # Modern GPT-6.1 Sol: Write = 1.25x, Read = 0.05x
    c_write_sol = (10000 * 1.25 * 2.50) / 1_000_000
    c_read_sol = (10000 * 0.05 * 2.50) / 1_000_000
    sol_10 = c_write_sol + 9 * c_read_sol

    table.add_row("Uncached (Baseline)", f"${uncached_10/10:.5f}", f"${uncached_10/10:.5f}", f"${uncached_10:.5f}", "0% (Baseline)")
    table.add_row("Classic Implicit (50% read)", f"${c_write_classic:.5f}", f"${c_read_classic:.5f}", f"${classic_10:.5f}", f"{((uncached_10 - classic_10)/uncached_10)*100:.1f}%")
    table.add_row("Modern GPT-6 Explicit (90% read)", f"${c_write_gpt6:.5f}", f"${c_read_gpt6:.5f}", f"${gpt6_10:.5f}", f"{((uncached_10 - gpt6_10)/uncached_10)*100:.1f}%")
    table.add_row("GPT-6.1 Sol Explicit (95% read)", f"${c_write_sol:.5f}", f"${c_read_sol:.5f}", f"${sol_10:.5f}", f"[bold]{((uncached_10 - sol_10)/uncached_10)*100:.1f}%[/bold]")

    console.print(table)


def explain_prompt_cache_diagnostics():
    """Display the Prompt Cache Diagnostics taxonomy from OpenAI's official diagnostics guide."""
    table = Table(title="OpenAI Prompt Cache Diagnostics Taxonomy (comparison_response_id)")
    table.add_column("Diagnostic Type", style="cyan")
    table.add_column("Reason Code", style="yellow")
    table.add_column("Root Cause", style="white")
    table.add_column("Remediation / Best Practice", style="green")

    taxonomies = [
        ("cache_miss", "tools_changed", "Tools added, removed, reordered, or schema mutated", "Keep tool list and JSON schema deterministically sorted; use tool_choice='none' or allowed_tools"),
        ("cache_miss", "model_changed", "Routing, fallback, or A/B test selected another model", "Pin model name; ensure cache-sharing requests route to identical model version"),
        ("cache_miss", "prompt_cache_key_changed", "Key changed between requests", "Keep stable prompt_cache_key per tenant/workflow; avoid random UUIDs"),
        ("cache_miss", "input_changed", "Timestamp, user ID, or dynamic token injected in prefix", "Move volatile data after the prefix or to user message; keep prefix byte-identical"),
        ("cache_miss", "reasoning_effort_changed", "Top-level reasoning.effort modified", "Use configuration_update input item mid-conversation on GPT-6 models"),
        ("cache_miss", "text_format_changed", "Output format / Structured Output schema changed", "Keep text.format and JSON schema identical across requests"),
        ("cache_miss", "context_compacted", "Compaction replaced earlier conversation history", "Preserve stable instructions before compacted summary"),
        ("cache_miss", "service_tier_changed", "Scale-tier or default routing tier switched", "Ensure service_tier is consistent across pipeline"),
        ("cache_hit", "N/A", "Expected prefix successfully matched and reused", "Inspect usage.input_tokens_details.cached_tokens for actual token count"),
    ]

    for diag_type, reason, root_cause, fix in taxonomies:
        table.add_row(diag_type, reason, root_cause, fix)

    console.print(table)


def main():
    try:
        demo_openai_prefix_caching()
    except Exception as e:
        console.print(f"[red]OpenAI caching error: {e}[/red]")

    console.print("\n")
    demo_openai_explicit_caching()

    console.print("\n")
    explain_prompt_cache_diagnostics()


if __name__ == "__main__":
    main()
