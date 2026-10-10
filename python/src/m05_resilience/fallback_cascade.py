"""Module 5: Multi-Provider Fallback Cascade.

Integrates Circuit Breakers and retries into a multi-tiered failover cascade:
1. Primary: Anthropic Claude 3.5 Sonnet
2. Secondary: OpenAI GPT-4o
3. Tertiary: Google Gemini 1.5 Flash
"""

from __future__ import annotations

import time
from typing import Callable, List, Tuple
from rich.console import Console
from src.m05_resilience.circuit_breaker import CircuitBreaker, CircuitBreakerOpenException
from src.m01_paradigms.client_factory import (
    get_anthropic_client,
    get_openai_client,
    get_gemini_client,
)

console = Console()


class ProviderNode:
    def __init__(self, name: str, invoker: Callable[[str], str]):
        self.name = name
        self.invoker = invoker
        self.breaker = CircuitBreaker(name=name, failure_threshold=2, recovery_timeout_seconds=15.0)

    def execute(self, prompt: str) -> str:
        self.breaker.before_call()
        try:
            result = self.invoker(prompt)
            self.breaker.record_success()
            return result
        except Exception as e:
            self.breaker.record_failure(e)
            raise e


class FallbackCascade:
    def __init__(self, providers: List[ProviderNode]):
        self.providers = providers

    def execute_with_failover(self, prompt: str) -> Tuple[str, str]:
        """Attempt each provider in sequence until one succeeds."""
        errors = []

        for provider in self.providers:
            try:
                console.print(f"[cyan]Attempting provider: {provider.name}...[/cyan]")
                res = provider.execute(prompt)
                return provider.name, res
            except CircuitBreakerOpenException as cbe:
                console.print(f"[yellow]Skipping {provider.name}: Breaker is OPEN.[/yellow]")
                errors.append(f"{provider.name} (Breaker OPEN)")
            except Exception as e:
                console.print(f"[red]Provider {provider.name} failed: {e}[/red]")
                errors.append(f"{provider.name} ({type(e).__name__})")

        raise RuntimeError(f"All providers in fallback cascade failed: {', '.join(errors)}")


# Concrete Provider Callers
def call_primary_anthropic(prompt: str) -> str:
    client = get_anthropic_client()
    res = client.messages.create(
        model="claude-3-5-haiku-20241022",
        max_tokens=150,
        messages=[{"role": "user", "content": prompt}],
    )
    return res.content[0].text  # type: ignore


def call_secondary_openai(prompt: str) -> str:
    client = get_openai_client()
    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=150,
    )
    return res.choices[0].message.content or ""


def call_tertiary_gemini(prompt: str) -> str:
    client = get_gemini_client()
    res = client.models.generate_content(
        model="gemini-1.5-flash",
        contents=prompt,
    )
    return res.text or ""


def main():
    console.print("\n[bold cyan]=== Multi-Provider Fallback Cascade Demonstration ===[/bold cyan]")
    cascade = FallbackCascade([
        ProviderNode("Anthropic_Claude", call_primary_anthropic),
        ProviderNode("OpenAI_GPT", call_secondary_openai),
        ProviderNode("Google_Gemini", call_tertiary_gemini),
    ])

    test_prompt = "Explain in one sentence why distributed circuit breakers prevent cascading failures."

    try:
        provider_used, result = cascade.execute_with_failover(test_prompt)
        console.print(f"\n[bold green]Success via {provider_used}:[/bold green]\n{result}")
    except Exception as e:
        console.print(f"[bold red]Cascade exhaustion:[/bold red] {e}")


if __name__ == "__main__":
    main()

