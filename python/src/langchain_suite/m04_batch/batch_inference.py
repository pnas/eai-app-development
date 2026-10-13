"""Module 4 (LangChain): Concurrent Batch Inference & Throttling Across Providers.

Contrasts provider-side 24-hour asynchronous Batch APIs with LangChain's
client-side concurrent batch execution across OpenAI, Anthropic, and Google Gemini:
1. Using model.abatch() / model.batch() with RunnableConfig(max_concurrency=N).
2. Avoiding rate-limit stampedes via client-side concurrency windows.
3. Gathering structured outputs in bulk with comparative benchmarking.
"""

from __future__ import annotations

import asyncio
import os
import time
from typing import List, Union
from rich.console import Console
from rich.table import Table

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from src.langchain_suite.core.models import get_chat_model

console = Console()

TELECOM_QUERIES = [
    "Customer reports 4G fallback in central Berlin despite 5G SA subscription.",
    "BSS billing cycle failed for subscriber ID SUB-4401 due to currency mismatch.",
    "eNodeB antenna tilt misconfiguration suspected on sector 3, tower DE-BER-102.",
    "Optical line terminal (OLT) reports loss of signal (LOS) on PON port 4.",
    "Roaming handshake timeout with partner network in Switzerland.",
    "VoLTE SIP 408 Request Timeout during peak hour traffic.",
]


def _has_key_for_provider(provider: str) -> bool:
    if provider == "openai":
        return bool(os.getenv("OPENAI_API_KEY"))
    if provider == "anthropic":
        return bool(os.getenv("ANTHROPIC_API_KEY"))
    if provider == "gemini":
        return bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
    return False


def _get_provider_model_name(provider: str) -> str:
    if provider == "openai":
        return os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    if provider == "anthropic":
        return os.getenv("ANTHROPIC_MODEL", "claude-haiku-5-5")
    if provider == "gemini":
        return os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
    return provider


async def run_batch_pipeline(
    providers: Union[List[str], str] = "all",
    max_concurrency: int = 3,
) -> List[dict]:
    """Executes queries concurrently using LangChain's abatch with concurrency throttling across providers."""
    if providers == "all":
        target_providers = ["openai", "anthropic", "gemini"]
    elif isinstance(providers, str):
        target_providers = [providers]
    else:
        target_providers = providers

    system_prompt = "You are a network operations assistant. Provide a 1-sentence recommended action."
    prompts = [
        [SystemMessage(content=system_prompt), HumanMessage(content=q)]
        for q in TELECOM_QUERIES
    ]

    console.print(f"\n[bold yellow]=== Module 4: Concurrent Batching Across Providers ===[/bold yellow]")
    console.print(f"[cyan]Target Providers: {target_providers} | Max Concurrency: {max_concurrency}[/cyan]\n")

    benchmarks: List[dict] = []

    for provider in target_providers:
        model_name = _get_provider_model_name(provider)
        console.print(f"\n[bold magenta]--- Provider: {provider.upper()} ({model_name}) ---[/bold magenta]")

        if not _has_key_for_provider(provider):
            console.print(f"[yellow][SKIPPED] Missing credentials for {provider}. Skipping live call.[/yellow]")
            benchmarks.append({
                "provider": provider,
                "model": model_name,
                "queries": len(prompts),
                "duration_sec": 0.0,
                "throughput": 0.0,
                "status": "SKIPPED",
            })
            continue

        try:
            model = get_chat_model(provider, temperature=0.0)
            start = time.perf_counter()

            config = RunnableConfig(max_concurrency=max_concurrency)
            results = await model.abatch(prompts, config=config)

            elapsed = time.perf_counter() - start
            throughput = len(prompts) / (elapsed if elapsed > 0 else 0.001)

            table = Table(title=f"{provider.upper()} Batch Results ({len(prompts)} queries in {elapsed:.2f}s, {throughput:.1f} q/s)")
            table.add_column("Query", style="cyan", max_width=45)
            table.add_column("Response", style="green", max_width=60)

            for query, response in zip(TELECOM_QUERIES, results):
                content = response.content if isinstance(response.content, str) else str(response.content)
                table.add_row(query, content.strip())

            console.print(table)

            benchmarks.append({
                "provider": provider,
                "model": model_name,
                "queries": len(prompts),
                "duration_sec": round(elapsed, 2),
                "throughput": round(throughput, 2),
                "status": "SUCCESS",
            })
        except Exception as e:
            console.print(f"[bold red]✘ {provider.upper()} batch execution failed: {e}[/bold red]")
            benchmarks.append({
                "provider": provider,
                "model": model_name,
                "queries": len(prompts),
                "duration_sec": 0.0,
                "throughput": 0.0,
                "status": "FAILED",
                "error": str(e),
            })

    # Summary Table
    summary_table = Table(title="Batch Inference Cross-Provider Performance Summary")
    summary_table.add_column("Provider", style="bold white")
    summary_table.add_column("Model", style="cyan")
    summary_table.add_column("Queries", justify="right")
    summary_table.add_column("Duration (s)", justify="right")
    summary_table.add_column("Throughput (q/s)", justify="right")
    summary_table.add_column("Status", style="bold")

    for b in benchmarks:
        status_style = "green" if b["status"] == "SUCCESS" else ("yellow" if b["status"] == "SKIPPED" else "red")
        dur_str = f"{b['duration_sec']:.2f}s" if b["status"] == "SUCCESS" else "N/A"
        tp_str = f"{b['throughput']:.1f}" if b["status"] == "SUCCESS" else "N/A"
        summary_table.add_row(
            b["provider"],
            b["model"],
            str(b["queries"]),
            dur_str,
            tp_str,
            f"[{status_style}]{b['status']}[/{status_style}]",
        )

    console.print("\n", summary_table)
    return benchmarks


if __name__ == "__main__":
    asyncio.run(run_batch_pipeline(providers="all", max_concurrency=3))
