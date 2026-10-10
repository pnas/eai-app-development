"""Lab 01 Reference Solution: Token Bucket Rate Limiter and Decorrelated Jitter."""

from __future__ import annotations

import asyncio
import inspect
import random
import time
from typing import Any, Callable, TypeVar

T = TypeVar("T")


class TokenBucket:
    """Thread-safe / Coroutine-safe Token Bucket Rate Limiter."""

    def __init__(self, capacity: float, refill_rate_per_sec: float) -> None:
        self.capacity = float(capacity)
        self.refill_rate = float(refill_rate_per_sec)
        self.tokens = float(capacity)
        self.last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    def _refill(self) -> None:
        """Calculate and add elapsed tokens up to capacity."""
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + (elapsed * self.refill_rate))
        self.last_refill = now

    async def acquire(self, tokens: float = 1.0) -> float:
        """Wait until `tokens` are available in the bucket, then consume them.

        Returns:
            The number of seconds waited.
        """
        if tokens > self.capacity:
            raise ValueError(f"Requested tokens ({tokens}) exceeds total capacity ({self.capacity})")

        total_waited = 0.0

        while True:
            async with self._lock:
                self._refill()
                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return total_waited

                # Calculate required sleep duration to reach needed tokens
                missing_tokens = tokens - self.tokens
                sleep_needed = missing_tokens / self.refill_rate

            # Sleep outside the lock so other tasks can refill/check
            await asyncio.sleep(sleep_needed)
            total_waited += sleep_needed


def calculate_decorrelated_jitter(
    base_delay: float,
    max_delay: float,
    previous_delay: float,
) -> float:
    """Calculate next retry backoff using decorrelated jitter.

    Formula: min(max_delay, uniform(base_delay, previous_delay * 3))
    """
    upper_bound = max(base_delay, previous_delay * 3.0)
    jittered = random.uniform(base_delay, upper_bound)
    return min(max_delay, jittered)


async def execute_with_resilience(
    api_call: Callable[[], Any],
    rate_limiter: TokenBucket,
    cost_tokens: float = 1.0,
    max_retries: int = 3,
    base_delay: float = 0.2,
    max_delay: float = 5.0,
) -> Any:
    """Execute an API call with proactive rate limiting and decorrelated jitter retry."""
    await rate_limiter.acquire(cost_tokens)

    delay = base_delay
    for attempt in range(max_retries + 1):
        try:
            res = api_call()
            if inspect.isawaitable(res):
                res = await res
            return res
        except Exception as exc:
            # Check for HTTP 429 status code or RateLimit in message
            status_code = getattr(exc, "status_code", getattr(exc, "status", None))
            is_rate_limit = (
                status_code == 429
                or "429" in str(exc)
                or "rate" in str(exc).lower()
            )

            if not is_rate_limit or attempt == max_retries:
                raise exc

            delay = calculate_decorrelated_jitter(base_delay, max_delay, delay)
            await asyncio.sleep(delay)
            # Re-acquire capacity before retrying
            await rate_limiter.acquire(cost_tokens)
