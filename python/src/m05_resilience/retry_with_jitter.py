"""Module 5: Exponential Backoff with Full Jitter.

Prevents the "Thundering Herd" problem by introducing randomness:
sleep = random.uniform(0, min(max_backoff, base * 2 ** attempt))
"""

from __future__ import annotations

import functools
import random
import time
from typing import Callable, TypeVar, Any
from rich.console import Console

console = Console()

T = TypeVar("T")


def retry_with_full_jitter(
    max_retries: int = 4,
    base_backoff_seconds: float = 1.0,
    max_backoff_seconds: float = 32.0,
    retryable_exceptions: tuple = (Exception,),
):
    """Decorator applying exponential backoff with full jitter to any callable."""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            attempt = 0
            while True:
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    attempt += 1
                    if attempt > max_retries:
                        console.print(f"[bold red]Exceeded max retries ({max_retries}) for {func.__name__}. Raising error.[/bold red]")
                        raise e

                    # Full Jitter formula: uniform random between 0 and min(max_backoff, base * 2^attempt)
                    ceiling = min(max_backoff_seconds, base_backoff_seconds * (2 ** attempt))
                    jittered_sleep = random.uniform(0, ceiling)

                    console.print(
                        f"[yellow]Attempt {attempt} failed ({type(e).__name__}: {e}). "
                        f"Backing off with Full Jitter: {jittered_sleep:.2f}s (ceiling: {ceiling:.1f}s)...[/yellow]"
                    )
                    time.sleep(jittered_sleep)

        return wrapper
    return decorator


def main():
    console.print("\n[bold cyan]=== Enterprise Retry with Full Jitter & Live OpenAI ===[/bold cyan]")
    console.print("[dim]Demonstrating exponential backoff and jitter under transient errors and injection after 2 attempts...[/dim]\n")

    from src.m01_paradigms.client_factory import get_openai_client
    import openai

    try:
        client = get_openai_client()
    except Exception as e:
        console.print(f"[yellow]⚠️  OpenAI client initialization skipped: {e}[/yellow]")
        client = None

    attempt_counter = 0

    @retry_with_full_jitter(
        max_retries=4,
        base_backoff_seconds=0.4,
        max_backoff_seconds=3.0,
        retryable_exceptions=(openai.RateLimitError, openai.APIConnectionError, openai.InternalServerError, ConnectionResetError),
    )
    def resilient_openai_call() -> str:
        nonlocal attempt_counter
        attempt_counter += 1
        console.print(f"[cyan]\n[Dispatch] Sending request to OpenAI gpt-4o-mini (Execution attempt #{attempt_counter})...[/cyan]")

        # INJECTION RULE: If after 2 attempts we don't get any error from OpenAI,
        # inject a simulated 429 RateLimitError to demonstrate full jitter backoff
        if attempt_counter <= 2:
            console.print(f"[magenta]   [Injection Check] Attempt #{attempt_counter}: Simulating transient 429 RateLimitError (no natural error encountered)...[/magenta]")
            import httpx
            req = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
            resp = httpx.Response(429, request=req, headers={"retry-after": "1.5"})
            raise openai.RateLimitError(
                "429 Too Many Requests: Rate limit reached for TPM quota on gpt-4o-mini (Injected for demonstration)",
                response=resp,
                body={"error": {"message": "Rate limit exceeded", "type": "tokens", "code": "rate_limit_exceeded"}},
            )

        if not client:
            return "200 OK: Fallback simulation response (OpenAI client not initialized)"

        # Live call to OpenAI model
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": "Explain the benefit of exponential backoff with full jitter in telecom API gateways in 1 concise sentence.",
                }
            ],
            max_tokens=60,
            temperature=0.2,
        )

        reply = (response.choices[0].message.content or "").strip()
        return f"200 OK ({response.model}): \"{reply}\""

    try:
        result = resilient_openai_call()
        console.print(f"\n[bold green][OK] Final Success:[/bold green] {result}\n")
    except Exception as err:
        console.print(f"\n[bold red][FAILED] Exhausted all retry attempts:[/bold red] {err}\n")


if __name__ == "__main__":
    main()

