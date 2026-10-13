"""Unified LangChain Multi-Paradigm CLI.

Demonstrates all 6 core GenAI architectural paradigms through LangChain abstractions:
1. Unified Chat Models & Normalized Content Blocks (OpenAI, Anthropic, Gemini)
2. Grammar-Constrained Structured Outputs with Pydantic v2
3. Prompt Caching & Ephemeral Breakpoint Cost Optimization
4. High-Throughput Concurrent Batch Processing with Concurrency Windows
5. Resilience & Declarative Multi-Provider Fallback Cascades
6. Enterprise Gateways (OpenRouter / LiteLLM) & Dynamic Cost Routing

Supports both interactive terminal menu and flag-driven execution.
Supports live provider calls and offline simulated mock mode.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from typing import Optional

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt

from src.langchain_suite.m01_paradigms.unified_chat import compare_unified_chat
from src.langchain_suite.m02_structured.structured_output import run_structured_extraction, TelecomIncidentTriage
from src.langchain_suite.m03_caching.prompt_cache import run_caching_demo
from src.langchain_suite.m05_resilience.fallback_cascade import demonstrate_fallback_cascade
from src.langchain_suite.m05_resilience.rate_limited_chain import demonstrate_langchain_rate_limiting
from src.langchain_suite.m06_gateways.cost_router import demonstrate_routing
from src.langchain_suite.m06_gateways.gateway_orchestrator import run_gateway_orchestration_demo

console = Console()

PARADIGM_TITLES = {
    "1": "Paradigm 1: Unified Chat, Streaming & Telemetry (OpenAI, Anthropic, Gemini)",
    "2": "Paradigm 2: Grammar-Constrained Structured Output (Pydantic v2)",
    "3": "Paradigm 3: Prompt Caching & Ephemeral Breakpoint Economics",
    "4": "Paradigm 4: Concurrent Batch Processing & Rate-Limit Windows",
    "5": "Paradigm 5: Resilience & Multi-Provider Fallback Cascades",
    "6": "Paradigm 6: Enterprise Gateways & Dynamic Cost-Based Routing",
}


def run_paradigm_1(provider: str = "all", custom_query: Optional[str] = None) -> None:
    """Executes Paradigm 1: Unified Chat & Streaming."""
    console.print(Panel.fit(
        "[bold cyan]Paradigm 1: Unified Chat Models, Streaming & Normalized Messages[/bold cyan]\n"
        "LangChain normalizes vendor payloads into SystemMessage / HumanMessage / AIMessage\n"
        "and exposes a uniform .stream() iterator with token callback telemetry.",
        title="Paradigm 1",
        border_style="cyan",
    ))
    sys_prompt = "You are an enterprise telecom assistant. Be concise and technical."
    query = custom_query or "Explain in 2 sentences why fiber optic lines have lower attenuation than copper coaxial cable."

    # If mock provider or no keys at all
    keys_present = any(os.getenv(k) for k in ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"])
    if provider == "mock" or not keys_present:
        console.print("[yellow]Executing in SIMULATED MOCK MODE (no external API keys required):[/yellow]\n")
        table = Table(title="Unified LangChain Provider Comparison (Mock Simulation)")
        table.add_column("Provider", style="cyan")
        table.add_column("Model Abstraction", style="yellow")
        table.add_column("Normalized Stream", style="green")
        table.add_column("Tokens (In/Out)", justify="right")
        table.add_column("Status", style="green")

        rows = [
            ("OPENAI", "gpt-4.1-mini", "Fiber cables use total internal reflection with minimal signal absorption.", "28 / 18", "SUCCESS"),
            ("ANTHROPIC", "claude-haiku-5-5", "Glass optical fibers prevent electromagnetic interference and radiative losses.", "28 / 17", "SUCCESS"),
            ("GEMINI", "gemini-3.8-flash", "Photons traveling through silica core experience orders of magnitude less resistance than electrons in copper.", "28 / 21", "SUCCESS"),
        ]
        for p, m, s, t, st in rows:
            table.add_row(p, m, s, t, st)
        console.print(table)
        console.print("\n[bold]Telemetry Audit Summary:[/bold] {'invocations': 3, 'total_tokens': 140, 'total_cost_usd': '$0.000042'}")
        return

    compare_unified_chat(query, sys_prompt)


def run_paradigm_2(provider: str = "openai") -> None:
    """Executes Paradigm 2: Structured Outputs with Pydantic v2."""
    console.print(Panel.fit(
        "[bold green]Paradigm 2: Grammar-Constrained Structured Outputs with Pydantic v2[/bold green]\n"
        "Leverages .with_structured_output() to enforce strict schema adherence at decoding time.",
        title="Paradigm 2",
        border_style="green",
    ))
    sample_report = """
    URGENT OUTAGE REPORT: Incident TICKET-9942 reported at 14:22 UTC.
    Multiple eNodeB base stations in Frankfurt South cluster lost synchronization.
    Fiber backhaul rings experiencing 45% packet drop after third-party roadwork severed secondary dark fiber conduit.
    Voice IMS calls dropping; estimated 18,500 active mobile subscribers experiencing service degradation.
    """

    if provider == "mock" or not os.getenv("OPENAI_API_KEY"):
        console.print("[yellow]OPENAI_API_KEY not found or mock selected. Showing validated Pydantic v2 instance:[/yellow]")
        triage = TelecomIncidentTriage(
            incident_id="TICKET-9942",
            severity="P1-CRITICAL",
            affected_subsystems=["5G-RAN", "FIBER-BACKHAUL", "IMS-VOICE"],
            root_cause_hypothesis="Third-party roadwork excavation severed secondary dark fiber conduit causing sync loss.",
            recommended_action="Reroute traffic to tertiary microwave link and dispatch fiber splicing emergency crew.",
            estimated_impact_subscribers=18500,
        )
    else:
        triage = run_structured_extraction(sample_report)

    console.print(Panel.fit(
        f"[bold green]Ticket:[/bold green] {triage.incident_id}\n"
        f"[bold red]Severity:[/bold red] {triage.severity}\n"
        f"[bold yellow]Subsystems:[/bold yellow] {', '.join(triage.affected_subsystems)}\n"
        f"[bold cyan]Subscribers Affected:[/bold cyan] {triage.estimated_impact_subscribers:,}\n"
        f"[bold white]Hypothesis:[/bold white] {triage.root_cause_hypothesis}\n"
        f"[bold magenta]Playbook Action:[/bold magenta] {triage.recommended_action}",
        title="Parsed Telecom Incident (Pydantic v2)",
        border_style="green",
    ))


def run_paradigm_3(provider: str = "anthropic") -> None:
    """Executes Paradigm 3: Prompt Caching & Ephemeral Breakpoint Economics."""
    console.print(Panel.fit(
        "[bold yellow]Paradigm 3: Prompt Caching & Ephemeral Breakpoint Economics[/bold yellow]\n"
        "Injects {'cache_control': {'type': 'ephemeral'}} in SystemMessage content blocks.\n"
        "Subsequent requests reusing identical prefixes receive ~90% cost discount and lower latency.",
        title="Paradigm 3",
        border_style="yellow",
    ))

    if provider == "mock" or not os.getenv("ANTHROPIC_API_KEY"):
        console.print("[yellow]ANTHROPIC_API_KEY not set or mock mode selected. Displaying telemetry comparison:[/yellow]\n")
        table = Table(title="Prompt Cache Simulation (Anthropic Claude Haiku 5.5)")
        table.add_column("Turn", style="cyan")
        table.add_column("State", style="yellow")
        table.add_column("Input Tokens", justify="right")
        table.add_column("Cache Creation", justify="right", style="green")
        table.add_column("Cache Read", justify="right", style="blue")
        table.add_column("Token Cost Rate", justify="right")

        table.add_row("Turn 1", "Cache Miss (Cold)", "1,248", "1,248", "0", "100% standard rate")
        table.add_row("Turn 2", "Cache Hit (Warm)", "1,254", "0", "1,248", "10% rate (90% discount!)")
        console.print(table)
        return

    run_caching_demo()


def run_paradigm_4(provider: str = "openai", concurrency: int = 3) -> None:
    """Executes Paradigm 4: High-Throughput Concurrent Batch Processing."""
    console.print(Panel.fit(
        f"[bold magenta]Paradigm 4: Concurrent Batch Inference (Concurrency Window = {concurrency})[/bold magenta]\n"
        "Uses model.abatch() / model.batch() with RunnableConfig(max_concurrency=N)\n"
        "to maximize throughput while strictly honoring upstream provider TPM/RPM rate limits.",
        title="Paradigm 4",
        border_style="magenta",
    ))

    if provider == "mock" or not os.getenv("OPENAI_API_KEY"):
        console.print("[yellow]Simulating concurrent batch execution across 5 telecom queries:[/yellow]\n")
        queries = [
            ("Customer reports 4G fallback in central Berlin despite 5G SA subscription.", "Trigger PCRF QoS profile refresh and verify 5G provisioning flag."),
            ("BSS billing cycle failed for subscriber ID SUB-4401 due to currency mismatch.", "Initiate foreign exchange conversion adapter and retry invoice generation."),
            ("eNodeB antenna tilt misconfiguration suspected on sector 3, tower DE-BER-102.", "Dispatch remote electrical tilt (RET) adjustment via OSS telemetry."),
            ("Optical line terminal (OLT) reports loss of signal (LOS) on PON port 4.", "Dispatch field technician to inspect splitter cabinet 14-B."),
            ("Roaming handshake timeout with partner network in Switzerland.", "Verify Diameter routing agent (DRA) reachability and S9 interface timers."),
        ]
        table = Table(title=f"Batch Results (5 queries executed in concurrency window {concurrency})")
        table.add_column("Query", style="cyan", max_width=45)
        table.add_column("Recommended Action", style="green", max_width=60)
        for q, a in queries:
            table.add_row(q, a)
        console.print(table)
        return

    asyncio.run(run_batch_pipeline(max_concurrency=concurrency))


def run_paradigm_5(simulate_failure: bool = True) -> None:
    """Executes Paradigm 5: Resilience & Multi-Provider Fallback Cascades."""
    console.print(Panel.fit(
        "[bold red]Paradigm 5: Resilience, Fallback Cascades & Token Rate Limiting[/bold red]\n"
        "Declarative failover via primary.with_fallbacks([secondary, tertiary]).\n"
        "Pre-call token bucket rate limiting (WSO2 pattern) with automatic failover.",
        title="Paradigm 5",
        border_style="red",
    ))
    demonstrate_fallback_cascade(simulate_failure=simulate_failure)
    demonstrate_langchain_rate_limiting()


def run_paradigm_6(simulate: bool = False) -> None:
    """Executes Paradigm 6: Enterprise Gateways & Cost Routing."""
    console.print(Panel.fit(
        "[bold blue]Paradigm 6: Enterprise Gateways & Dynamic Cost-Based Routing[/bold blue]\n"
        "Routes requests dynamically based on query complexity (Economy vs Reasoning)\n"
        "and interfaces with unified proxy gateways (OpenRouter, LiteLLM Proxy).",
        title="Paradigm 6",
        border_style="blue",
    ))
    demonstrate_routing(simulate=simulate)
    console.print("\n[bold cyan]--- Gateway Orchestration (OpenRouter / LiteLLM) ---[/bold cyan]")
    run_gateway_orchestration_demo(simulate=simulate)


def run_all(provider: str = "mock") -> None:
    """Runs all 6 paradigms sequentially."""
    console.print("[bold yellow]" + "=" * 78 + "[/bold yellow]")
    console.print("[bold yellow]     RUNNING COMPLETE 6-PARADIGM SUITE VIA LANGCHAIN ABSTRACTIONS            [/bold yellow]")
    console.print("[bold yellow]" + "=" * 78 + "[/bold yellow]\n")

    is_simulated = (provider == "mock")
    run_paradigm_1(provider=provider)
    console.print("\n" + "=" * 75 + "\n")
    run_paradigm_2(provider=provider)
    console.print("\n" + "=" * 75 + "\n")
    run_paradigm_3(provider=provider)
    console.print("\n" + "=" * 75 + "\n")
    run_paradigm_4(provider=provider)
    console.print("\n" + "=" * 75 + "\n")
    run_paradigm_5(simulate_failure=True)
    console.print("\n" + "=" * 75 + "\n")
    run_paradigm_6(simulate=is_simulated)
    console.print("\n[bold green][OK] All 6 paradigms executed successfully![/bold green]\n")


def interactive_menu() -> None:
    """Presents an interactive selector for the user in the terminal."""
    while True:
        console.print("\n[bold cyan]+" + "=" * 76 + "+[/bold cyan]")
        console.print("[bold cyan]|          LangChain Multi-Paradigm Integration Suite CLI            |[/bold cyan]")
        console.print("[bold cyan]+" + "=" * 76 + "+[/bold cyan]")
        console.print("  [bold yellow]1[/bold yellow] - Paradigm 1: Unified Chat, Streaming & Telemetry (OpenAI, Anthropic, Gemini)")
        console.print("  [bold yellow]2[/bold yellow] - Paradigm 2: Grammar-Constrained Structured Output (Pydantic v2)")
        console.print("  [bold yellow]3[/bold yellow] - Paradigm 3: Prompt Caching & Ephemeral Breakpoint Economics")
        console.print("  [bold yellow]4[/bold yellow] - Paradigm 4: Concurrent Batch Processing & Rate-Limit Windows")
        console.print("  [bold yellow]5[/bold yellow] - Paradigm 5: Resilience & Multi-Provider Fallback Cascades")
        console.print("  [bold yellow]6[/bold yellow] - Paradigm 6: Enterprise Gateways & Cost-Based Routing")
        console.print("  [bold yellow]A[/bold yellow] - Run ALL 6 Paradigms in Sequence")
        console.print("  [bold yellow]Q[/bold yellow] - Exit\n")

        choice = Prompt.ask("Select an option", choices=["1", "2", "3", "4", "5", "6", "A", "a", "Q", "q"], default="A")

        if choice.lower() == "q":
            console.print("[green]Goodbye![/green]")
            break
        elif choice.lower() == "a":
            run_all(provider="auto")
        elif choice == "1":
            run_paradigm_1(provider="auto")
        elif choice == "2":
            run_paradigm_2(provider="auto")
        elif choice == "3":
            run_paradigm_3(provider="auto")
        elif choice == "4":
            run_paradigm_4(provider="auto")
        elif choice == "5":
            run_paradigm_5(simulate_failure=True)
        elif choice == "6":
            run_paradigm_6()

        Prompt.ask("\nPress Enter to return to the menu...")


def main() -> None:
    parser = argparse.ArgumentParser(description="LangChain 6-Paradigm Architecture CLI Showcase")
    parser.add_argument(
        "-p", "--paradigm",
        choices=["1", "2", "3", "4", "5", "6", "all"],
        help="Specify which paradigm to execute (1-6 or all)",
    )
    parser.add_argument(
        "--provider",
        choices=["mock", "openai", "anthropic", "gemini", "all", "auto"],
        default="auto",
        help="Target provider or mock mode for offline demonstration (default: auto)",
    )
    parser.add_argument("-q", "--query", type=str, default=None, help="Optional custom query for Paradigms 1 & 4")
    parser.add_argument("-c", "--concurrency", type=int, default=3, help="Max concurrency for Paradigm 4")
    parser.add_argument("-i", "--interactive", action="store_true", help="Launch interactive menu mode")

    args = parser.parse_args()

    # If no flags passed, launch interactive menu
    if len(sys.argv) == 1 or args.interactive:
        interactive_menu()
        return

    target_provider = args.provider
    if target_provider == "auto":
        # Check if any provider key is present
        has_keys = any(os.getenv(k) for k in ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"])
        if not has_keys:
            target_provider = "mock"

    if args.paradigm == "all":
        run_all(provider=target_provider)
    elif args.paradigm == "1":
        run_paradigm_1(provider=target_provider, custom_query=args.query)
    elif args.paradigm == "2":
        run_paradigm_2(provider=target_provider)
    elif args.paradigm == "3":
        run_paradigm_3(provider=target_provider)
    elif args.paradigm == "4":
        run_paradigm_4(provider=target_provider, concurrency=args.concurrency)
    elif args.paradigm == "5":
        run_paradigm_5(simulate_failure=True)
    elif args.paradigm == "6":
        run_paradigm_6()


if __name__ == "__main__":
    main()
