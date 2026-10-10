"""Module 3: Google Gemini Context Caching.

Demonstrates creating an explicit CachedContent resource with a custom TTL,
querying against the cached resource, and cleaning up.
"""

from __future__ import annotations

import datetime
from rich.console import Console
from google.genai import types as gemini_types
from src.m01_paradigms.client_factory import get_gemini_client

console = Console()


def demo_gemini_context_cache():
    client = get_gemini_client()
    model = "gemini-1.5-flash"

    console.print("\n[bold green]=== Google Gemini Explicit Context Caching ===[/bold green]")
    console.print("Creating synthetic long context document for caching (>32k tokens)...")

    # Synthetic document of ~33,000 tokens
    base_text = "Telekom Enterprise Network Infrastructure Specification. Node cluster policy 10.0.0.1. "
    large_content = base_text * 3000

    console.print(f"Document generated (~{len(large_content.split())} words). Creating Cache resource...")

    try:
        # Create an explicit cache resource with 10-minute TTL
        cache = client.caches.create(
            model=model,
            config=gemini_types.CreateCachedContentConfig(
                contents=[large_content],
                system_instruction="You are an infrastructure expert referencing this network spec.",
                ttl="600s", # 10 minutes
                display_name="telekom_network_spec_cache",
            ),
        )
        console.print(f"[green]Cache created successfully![/green] Name: {cache.name}, Expires: {cache.expire_time}")

        # Query using the cached content resource
        response = client.models.generate_content(
            model=model,
            contents="What is the cluster policy IP mentioned in the document?",
            config=gemini_types.GenerateContentConfig(
                cached_content=cache.name,
            ),
        )
        console.print(f"[bold]Response:[/bold] {response.text}")

        if response.usage_metadata:
            cached_count = getattr(response.usage_metadata, "cached_content_token_count", 0)
            console.print(f"[bold green]Cached Tokens Read:[/bold green] {cached_count}")

        # Clean up
        client.caches.delete(name=cache.name)
        console.print("[dim]Cache resource deleted.[/dim]")

    except Exception as e:
        console.print(f"[yellow]Context caching note (requires tier access or >=32,768 tokens):[/yellow] {e}")


def main():
    demo_gemini_context_cache()


if __name__ == "__main__":
    main()

