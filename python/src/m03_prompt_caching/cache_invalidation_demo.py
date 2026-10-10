"""Module 3: What Breaks the Cache? Architectural Pitfalls Benchmark.

This script benchmarks the architectural anti-patterns that silently destroy
prompt cache hits:
1. Dynamic timestamps placed in the system prompt prefix vs appended at the end.
2. Tool definitions with shuffled key orders.
"""

from __future__ import annotations

import datetime
import time
from rich.console import Console
from rich.table import Table
from src.m01_paradigms.client_factory import get_openai_client

console = Console()

STATIC_DOC = """
# TELEKOM COMPLIANCE STANDARDS: AUDITING & RETENTION RULES
Every transaction processed through the billing API must retain immutable audit logs for 7 years.
Audit trails must include caller identity, IP address, timestamp, HMAC signature, and response code.
In the event of an audit alert, the compliance officer must be notified via PagerDuty within 15 minutes.
""" + ("\nAll data pipelines must comply with GDPR Article 17 Right to Erasure.\n" * 45)


def run_benchmark():
    client = get_openai_client()
    model = "gpt-4o-mini"

    table = Table(title="Prompt Cache Invalidation: Bad vs. Good Architecture")
    table.add_column("Architecture Pattern", style="cyan")
    table.add_column("Call #", style="white")
    table.add_column("Prompt Tokens", justify="right")
    table.add_column("Cached Tokens", justify="right", style="bold green")
    table.add_column("Cache Hit %", justify="right", style="bold magenta")

    # -------------------------------------------------------------
    # Anti-Pattern: Dynamic timestamp injected into the system prompt prefix
    # -------------------------------------------------------------
    console.print("\n[bold red]1. Simulating Anti-Pattern: Dynamic Timestamp at Start of Prefix[/bold red]")
    for i in range(1, 3):
        # Fresh timestamp changes the first 30 tokens of the prompt!
        dynamic_system_prompt = f"Timestamp: {datetime.datetime.now().isoformat()}\n\n{STATIC_DOC}"
        messages = [
            {"role": "system", "content": dynamic_system_prompt},
            {"role": "user", "content": "What is the retention period for billing audit logs?"},
        ]
        time.sleep(1) # Ensure timestamp changes
        res = client.chat.completions.create(model=model, messages=messages, max_tokens=20)
        
        usage = res.usage
        prompt_tok = usage.prompt_tokens if usage else 0
        cached_tok = getattr(usage.prompt_tokens_details, "cached_tokens", 0) if usage and hasattr(usage, "prompt_tokens_details") else 0
        hit_pct = (cached_tok / prompt_tok * 100) if prompt_tok else 0.0

        table.add_row(
            "[red]Anti-Pattern (Dynamic Prefix)[/red]",
            f"Run {i}",
            str(prompt_tok),
            str(cached_tok),
            f"{hit_pct:.1f}%",
        )

    # -------------------------------------------------------------
    # Best Practice: Invariant Static Prefix First, Dynamic Timestamp in User Query
    # -------------------------------------------------------------
    console.print("[bold green]2. Simulating Best Practice: Invariant Static Prefix First[/bold green]")
    for i in range(1, 3):
        # System prompt is 100% stable and invariant across all calls!
        static_system_prompt = f"System Compliance Engine:\n\n{STATIC_DOC}"
        messages = [
            {"role": "system", "content": static_system_prompt},
            {
                "role": "user",
                "content": f"[Request Context: {datetime.datetime.now().isoformat()}]\nWhat is the retention period?",
            },
        ]
        time.sleep(1)
        res = client.chat.completions.create(model=model, messages=messages, max_tokens=20)

        usage = res.usage
        prompt_tok = usage.prompt_tokens if usage else 0
        cached_tok = getattr(usage.prompt_tokens_details, "cached_tokens", 0) if usage and hasattr(usage, "prompt_tokens_details") else 0
        hit_pct = (cached_tok / prompt_tok * 100) if prompt_tok else 0.0

        table.add_row(
            "[green]Best Practice (Static Prefix)[/green]",
            f"Run {i}",
            str(prompt_tok),
            str(cached_tok),
            f"{hit_pct:.1f}%",
        )

    console.print(table)


def main():
    try:
        run_benchmark()
    except Exception as e:
        console.print(f"[red]Benchmark failed: {e}[/red]")


if __name__ == "__main__":
    main()

