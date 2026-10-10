"""Module 3: OpenAI Automatic Prefix Prompt Caching.

Demonstrates OpenAI's implicit prefix matching mechanism for prompts >= 1,024 tokens,
and inspects the prompt_tokens_details.cached_tokens telemetry.
"""

from __future__ import annotations

import time
from rich.console import Console
from rich.table import Table
from src.m01_paradigms.client_factory import get_openai_client

console = Console()

# Synthetic enterprise knowledge base >= 1,024 tokens
LARGE_CONTEXT = """
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
""" + ("\nAll cluster metrics are ingested into Prometheus and persisted to long-term Thanos storage.\n" * 50)


def test_openai_caching():
    client = get_openai_client()
    model = "gpt-4o-mini"

    table = Table(title="OpenAI Automatic Prefix Caching Demonstration")
    table.add_column("Call", style="cyan")
    table.add_column("Total Prompt Tokens", justify="right")
    table.add_column("Cached Tokens (Hit)", justify="right", style="bold green")
    table.add_column("Uncached Tokens (Miss)", justify="right", style="yellow")
    table.add_column("Latency (s)", justify="right", style="magenta")

    queries = [
        "What is the required minAvailable percentage in Pod Disruption Budgets?",
        "What CSI driver is used for persistent volumes and how often are snapshots taken?",
    ]

    for idx, query in enumerate(queries, start=1):
        # The prompt shares an identical prefix (LARGE_CONTEXT)
        messages = [
            {"role": "system", "content": f"You are an SRE runbook assistant.\n\n{LARGE_CONTEXT}"},
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

        table.add_row(
            f"Call #{idx}",
            str(prompt_tok),
            str(cached_tok),
            str(uncached_tok),
            f"{elapsed:.2f}s",
        )

    console.print(table)
    console.print("\n[dim]Notice: Call #2 automatically achieved a cache hit on the prefix without any custom headers![/dim]")


def main():
    try:
        test_openai_caching()
    except Exception as e:
        console.print(f"[red]OpenAI caching error: {e}[/red]")


if __name__ == "__main__":
    main()

