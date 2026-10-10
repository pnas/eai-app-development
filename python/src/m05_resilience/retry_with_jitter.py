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
    console.print("\n[bold cyan]=== Simulating Retry with Full Jitter ===[/bold cyan]")
    call_count = 0

    @retry_with_full_jitter(max_retries=3, base_backoff_seconds=0.5, max_backoff_seconds=4.0)
    def flaky_llm_api_call():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ConnectionResetError("429 Too Many Requests: TPM quota exceeded")
        return "200 OK: LLM response received successfully!"

    result = flaky_llm_api_call()
    console.print(f"[bold green]Result:[/bold green] {result}")


if __name__ == "__main__":
    main()

