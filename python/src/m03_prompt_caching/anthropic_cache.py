"""Module 3: Anthropic Explicit Prompt Caching.

Demonstrates using explicit cache_control breakpoints ({"type": "ephemeral"}),
inspecting cache creation vs cache read tokens, and observing latency reduction.
"""

from __future__ import annotations

import time
from rich.console import Console
from rich.table import Table
from src.m01_paradigms.client_factory import get_anthropic_client

console = Console()

# Generates synthetic large context (>1,024 tokens to meet Claude 3.5 Sonnet threshold)
LARGE_POLICY_DOC = """
# TELEKOM ENTERPRISE CLOUD GOVERNANCE & RESILIENCE MANUAL (v4.2)
[Section 1: Distributed Architecture Standards]
All microservices must implement distributed tracing with OpenTelemetry and propagate W3C trace context.
All internal synchronous RPCs must enforce timeouts of max 1,500ms and retry only on idempotency-safe methods.
[Section 2: Database and Sharding Architecture]
PostgreSQL instances must be provisioned across at least 3 Availability Zones with automatic failover.
Write operations must never bypass the primary leader node. Read replicas must be load-balanced with max replication lag of 250ms.
[Section 3: Security & Data Classification]
PII (Personally Identifiable Information) must be encrypted at rest with customer-managed KMS keys.
All API endpoints exposed to the public internet must enforce TLS 1.3 with mutual authentication for B2B partners.
""" + ("\nAll microservices must undergo chaos testing quarterly and verify graceful degradation under 50% packet loss.\n" * 50)


def run_caching_simulation():
    client = get_anthropic_client()
    model = "claude-3-5-sonnet-20241022"

    table = Table(title="Anthropic Prompt Caching Execution Log")
    table.add_column("Turn", style="cyan")
    table.add_column("Query", style="white")
    table.add_column("Input Tokens", justify="right")
    table.add_column("Cache Write Tok", justify="right", style="yellow")
    table.add_column("Cache Read Tok", justify="right", style="bold green")
    table.add_column("Latency (s)", justify="right", style="magenta")

    queries = [
        "What is the maximum allowed replication lag for read replicas?",
        "What are the quarterly testing requirements for microservices?",
        "What TLS version is mandatory for public API endpoints?",
    ]

    # Breakpoint placement: On the large static system document
    system_with_cache = [
        {
            "type": "text",
            "text": LARGE_POLICY_DOC,
            "cache_control": {"type": "ephemeral"},  # <-- Breakpoint 1
        }
    ]

    conversation_history = []

    for i, q in enumerate(queries, start=1):
        conversation_history.append({"role": "user", "content": q})

        start_time = time.perf_counter()
        response = client.messages.create(
            model=model,
            max_tokens=256,
            system=system_with_cache,
            messages=conversation_history,
        )
        elapsed = time.perf_counter() - start_time

        usage = response.usage
        cache_write = getattr(usage, "cache_creation_input_tokens", 0)
        cache_read = getattr(usage, "cache_read_input_tokens", 0)

        table.add_row(
            f"Turn {i}",
            q[:35] + "...",
            str(usage.input_tokens),
            str(cache_write),
            str(cache_read),
            f"{elapsed:.2f}s",
        )

        # Append assistant reply to keep conversation state
        conversation_history.append({"role": "assistant", "content": response.content})

    console.print(table)
    console.print("\n[dim]Notice: Turn 1 creates the cache (write cost). Turns 2 & 3 hit the cache with 90% cost discount and lower latency![/dim]")


def main():
    try:
        run_caching_simulation()
    except Exception as e:
        console.print(f"[red]Anthropic cache error: {e}[/red]")


if __name__ == "__main__":
    main()

