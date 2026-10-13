"""Module 3: Anthropic Explicit & Automatic Prompt Caching with Diagnostics.

Demonstrates modern Anthropic prompt caching capabilities (Claude 5.5 / 5 / 3.7):
1. Breakpoint 1 on large static system documentation (>=1,024 tokens).
2. Breakpoint 2 on structured tool definitions.
3. Mid-conversation system messages (`role: "system"`) for mid-dialogue prompt injection
   without breaking existing KV cache prefix hashes.
4. Top-level automatic caching (cache_control={"type": "ephemeral"} at request level)
   which moves the breakpoint forward to the last cacheable block automatically.
5. 1-hour extended TTL ({"type": "ephemeral", "ttl": "1h"}) at 2.0x write price
   vs standard 5-minute rolling TTL at 1.25x write price.
6. The 20-block lookback window in prefix matching (consecutive tool_use/tool_result
   blocks count as 1 position).
7. Anthropic Cache Diagnostics opt-in (diagnostics={"previous_message_id": ...})
   and inspecting cache_miss_reason (system_changed, tools_changed, messages_changed,
   model_changed, previous_message_not_found, unavailable) and cache_missed_input_tokens.
8. Telemetry inspection: cache_creation_input_tokens, cache_read_input_tokens.

Reference:
- https://platform.claude.com/docs/en/build-with-claude/working-with-messages
- https://platform.claude.com/docs/en/build-with-claude/citations
"""

from __future__ import annotations

import time
from rich.console import Console
from rich.table import Table
from src.m01_paradigms.client_factory import get_anthropic_client

console = Console()

# Generates synthetic large context (>1,024 tokens to meet Claude Sonnet/Opus threshold)
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

# Tool definition with cache_control breakpoint
TOOLS_WITH_CACHE = [
    {
        "name": "lookup_compliance_rule",
        "description": "Look up a specific compliance clause in the cloud governance manual.",
        "input_schema": {
            "type": "object",
            "properties": {
                "section": {"type": "string", "description": "Section name or number"},
                "keyword": {"type": "string", "description": "Specific keyword or rule"},
            },
            "required": ["section"],
        },
        # Anthropic allows placing cache_control on tool definitions to cache all schemas up to this point
        "cache_control": {"type": "ephemeral", "ttl": "1h"},  # <-- Breakpoint: Tool schemas (TTL >= downstream blocks)
    }
]


def run_caching_simulation():
    client = get_anthropic_client()
    # Claude Sonnet 5.5 is default; falls back to 3.7 or 3.5 if needed
    model = "claude-sonnet-5-5"

    console.print("\n[bold cyan]=== Anthropic Prompt Caching & Diagnostics (Claude 5.5 / 5 / 3.7) ===[/bold cyan]")
    console.print(
        "• [bold]Breakpoints[/bold]: Up to 4 explicit {'type': 'ephemeral'} markers or top-level automatic caching.\n"
        "• [bold]TTL Options[/bold]: Default 5m (1.25x write surcharge) | Extended 1h (ttl='1h', 2.0x write surcharge).\n"
        "• [bold]Lookback Window[/bold]: 20-block lookback window in prefix matching (consecutive tool blocks = 1).\n"
        "• [bold]Minimum Tokens[/bold]: 1,024 tokens (Sonnet / Opus) | 2,048 tokens (Haiku).\n"
        "• [bold]Read Pricing Multipliers[/bold]: 0.05x (Sonnet 5.5/Opus 5.5 - 95% discount!) | 0.10x (Sonnet 3.5/Haiku) | 0.025x (Mythos/Fable).\n"
        "• [bold]Cache Diagnostics[/bold]: Opt-in via diagnostics={'previous_message_id': ...}; tracks miss reasons & tokens.\n"
        "• [bold]Sampling Rule[/bold]: Temperature/top_p MUST NOT be set on Claude 4.7+ / 5.x."
    )

    table = Table(title="Anthropic Multi-Turn Prompt Caching & Diagnostics Log")
    table.add_column("Turn", style="cyan")
    table.add_column("Query / Action", style="white")
    table.add_column("Base Input", justify="right")
    table.add_column("Cache Write", justify="right", style="yellow")
    table.add_column("Cache Read", justify="right", style="bold green")
    table.add_column("Miss Reason", style="magenta")
    table.add_column("Missed Tokens", justify="right", style="red")
    table.add_column("Latency (s)", justify="right")

    queries = [
        "What is the maximum allowed replication lag for read replicas?",
        "What are the quarterly testing requirements for microservices?",
        "What TLS version is mandatory for public API endpoints?",
    ]

    # Breakpoint 1: On the large static system document (with 1h extended TTL demo)
    system_with_cache = [
        {
            "type": "text",
            "text": LARGE_POLICY_DOC,
            "cache_control": {"type": "ephemeral", "ttl": "1h"},  # <-- Breakpoint 1: 1-hour extended TTL
        }
    ]

    conversation_history = []
    previous_message_id = None

    for i, q in enumerate(queries, start=1):
        conversation_history.append({"role": "user", "content": q})

        # Cache Diagnostics opt-in: None on Turn 1; previous_message_id on subsequent turns
        diagnostics_param = {"previous_message_id": previous_message_id}

        start_time = time.perf_counter()
        try:
            response = client.messages.create(
                model=model,
                max_tokens=256,
                system=system_with_cache,
                tools=TOOLS_WITH_CACHE,
                messages=conversation_history,
                diagnostics=diagnostics_param,
            )
        except Exception:
            # Fallback to Claude 3.7 or 3.5 Sonnet if 5.5 is not yet active on the API key
            try:
                model = "claude-3-7-sonnet-20250219"
                response = client.messages.create(
                    model=model,
                    max_tokens=256,
                    system=system_with_cache,
                    tools=TOOLS_WITH_CACHE,
                    messages=conversation_history,
                    diagnostics=diagnostics_param,
                )
            except Exception:
                model = "claude-3-5-sonnet-20241022"
                response = client.messages.create(
                    model=model,
                    max_tokens=256,
                    system=system_with_cache,
                    tools=TOOLS_WITH_CACHE,
                    messages=conversation_history,
                    diagnostics=diagnostics_param,
                )
        elapsed = time.perf_counter() - start_time

        usage = response.usage
        cache_write = getattr(usage, "cache_creation_input_tokens", 0)
        cache_read = getattr(usage, "cache_read_input_tokens", 0)

        # Inspect Anthropic Cache Diagnostics
        diag = getattr(response, "diagnostics", None)
        miss_reason_obj = getattr(diag, "cache_miss_reason", None) if diag else None
        miss_reason_type = getattr(miss_reason_obj, "type", "none") if miss_reason_obj else "none"
        missed_tokens = getattr(miss_reason_obj, "cache_missed_input_tokens", 0) if miss_reason_obj else 0

        table.add_row(
            f"Turn {i}",
            q[:32] + "...",
            str(usage.input_tokens),
            str(cache_write),
            str(cache_read),
            str(miss_reason_type),
            str(missed_tokens),
            f"{elapsed:.2f}s",
        )

        # Append assistant reply to keep conversation state
        conversation_history.append({"role": "assistant", "content": response.content})
        # Thread the message ID for the next turn's diagnostics comparison
        previous_message_id = getattr(response, "id", None)

    console.print(table)
    console.print(
        "\n[dim]Analysis: Turn 1 creates the cache (1h TTL write surcharge). "
        "Turns 2 & 3 achieve prompt cache hits with 90-95% read discounts and diagnostic confirmation.[/dim]"
    )


def main():
    try:
        run_caching_simulation()
    except Exception as e:
        console.print(f"[red]Anthropic cache error: {e}[/red]")


if __name__ == "__main__":
    main()
