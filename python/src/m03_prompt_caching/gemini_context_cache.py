"""Module 3: Google Gemini Context Caching.

Demonstrates Google Gemini Enterprise Agent Platform Context Caching:
1. Explicit Caching: Creating a CachedContent resource with custom TTL (min 1 min,
   default 60 min, no max limit), querying against it, and cleaning up.
   Eligible for a 90% discount on Gemini 2.5+ models (75% on Gemini 2.0).
   Minimum token threshold: 2,048 tokens (Gemini 2 family) / 4,096 tokens (Gemini 3 family).
2. Implicit Caching: Enabled by default across Google Cloud projects, providing
   an automatic 90% discount on cache hits with zero storage costs.
3. Security & Isolation: Scoped by GCP project number, VPC Service Controls supported,
   and agentic context scoping to prevent cross-user leakage.
"""

from __future__ import annotations

import datetime
from rich.console import Console
from google.genai import types as gemini_types
from src.m01_paradigms.client_factory import get_gemini_client

console = Console()

# Minimum token thresholds per Gemini Enterprise Agent Platform specs
GEMINI_2_MIN_CACHE_TOKENS = 2048
GEMINI_3_MIN_CACHE_TOKENS = 4096
GEMINI_3_IMPLICIT_PREVIEW_TOKENS = 6144


def demo_gemini_explicit_context_cache():
    """Demonstrate explicit context cache creation, query, and cleanup."""
    client = get_gemini_client()
    # Gemini 2.5 Flash supports explicit caching with 2,048 min tokens and 90% discount
    model = "gemini-2.5-flash"

    console.print("\n[bold green]=== Google Gemini Explicit Context Caching ===[/bold green]")
    console.print(f"Target model: [cyan]{model}[/cyan] (Threshold: {GEMINI_2_MIN_CACHE_TOKENS} tokens, 90% discount)")

    # Generate synthetic content meeting the Gemini 2 minimum threshold (>= 2,048 tokens, ~2,500 tokens here)
    base_text = (
        "Telekom Enterprise Network Infrastructure Specification v4.2. "
        "Core node cluster policy IP: 10.240.0.1. Failover gateway: 10.240.0.254. "
        "BGP Autonomous System Number: AS65001. VLAN ID: 4094. "
        "Latency SLA requirement: sub-5ms within regional metro area. "
    )
    # ~25 words per repeat * 100 repeats = ~2500 words (~3100 tokens, safely exceeding 2,048)
    large_content = base_text * 100

    console.print(f"Generated context payload (~{len(large_content.split())} words, >{GEMINI_2_MIN_CACHE_TOKENS} tokens).")
    console.print("Creating explicit Cache resource via client.caches.create()...")

    try:
        # Create an explicit cache resource (TTL: 10 minutes; default is 60 minutes)
        # Note: Max content size is 10 MB for text/blob; min TTL 1 minute, no maximum duration.
        cache = client.caches.create(
            model=model,
            config=gemini_types.CreateCachedContentConfig(
                contents=[large_content],
                system_instruction="You are a telecom infrastructure engineering assistant referencing this network spec.",
                ttl="600s",  # 10 minutes
                display_name="telekom_network_spec_cache_v4",
            ),
        )
        console.print(f"[green]Cache created successfully![/green] Name: {cache.name}, Expires: {cache.expire_time}")

        # Query using the cached content resource
        console.print("Querying Gemini using explicit cached_content reference...")
        response = client.models.generate_content(
            model=model,
            contents="What is the core node cluster policy IP and failover gateway mentioned in the document?",
            config=gemini_types.GenerateContentConfig(
                cached_content=cache.name,
            ),
        )
        console.print(f"[bold]Response:[/bold] {response.text}")

        if response.usage_metadata:
            cached_count = getattr(response.usage_metadata, "cached_content_token_count", 0)
            prompt_count = getattr(response.usage_metadata, "prompt_token_count", 0)
            console.print(
                f"[bold green]Usage Metadata:[/bold green] Prompt Tokens: {prompt_count}, "
                f"Cached Tokens Read: {cached_count}"
            )

        # Explicit cache management: delete when finished to avoid unnecessary storage costs
        client.caches.delete(name=cache.name)
        console.print("[dim]Cache resource deleted successfully.[/dim]")

    except Exception as e:
        console.print(
            f"[yellow]Explicit context caching notice (requires GCP billing/tier and >={GEMINI_2_MIN_CACHE_TOKENS} tokens):[/yellow] {e}"
        )


def demo_gemini_implicit_context_cache():
    """Explain implicit caching mechanisms and best practices in Gemini Enterprise Agent Platform."""
    console.print("\n[bold green]=== Google Gemini Implicit Caching Overview ===[/bold green]")
    console.print(
        "• [bold]Zero Configuration[/bold]: Enabled by default across all Google Cloud projects.\n"
        "• [bold]Discount[/bold]: 90% discount on cached input tokens (same as explicit for Gemini 2.5+).\n"
        "• [bold]Storage Cost[/bold]: $0.00 (no storage costs for implicit caches).\n"
        "• [bold]Thresholds[/bold]:\n"
        f"   - Gemini 2 family: {GEMINI_2_MIN_CACHE_TOKENS} tokens\n"
        f"   - Gemini 3 family: {GEMINI_3_MIN_CACHE_TOKENS} tokens "
        f"(6,144 tokens for 3.0 Flash Preview, 3.1 Pro Preview, 3.7 Flash, 3.8 Flash)\n"
        "• [bold]Optimization Tips[/bold]:\n"
        "   1. Place large, common prompt content strictly at token index 0 (prefix).\n"
        "   2. Send subsequent requests sharing the prefix in short temporal proximity.\n"
        "• [bold]Agentic Isolation & Security[/bold]:\n"
        "   - Caches are isolated by GCP project number; never shared cross-project.\n"
        "   - Scope multi-tenant agent caches to user execution context to prevent credential leakage.\n"
        "   - Full VPC Service Controls (VPC-SC) support."
    )


def main():
    demo_gemini_implicit_context_cache()
    demo_gemini_explicit_context_cache()


if __name__ == "__main__":
    main()


