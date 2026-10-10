"""Lab 01 Starter: Token Bucket Rate Limiter and Decorrelated Jitter.

Fill in the TODO sections below to complete the implementation.
"""

from __future__ import annotations

import asyncio
import random
import time
from typing import Callable, TypeVar

T = TypeVar("T")


class TokenBucket:
    """Thread-safe / Coroutine-safe Token Bucket Rate Limiter."""

    def __init__(self, capacity: float, refill_rate_per_sec: float) -> None:
        """Initialize the token bucket.

        Args:
            capacity: Maximum burst capacity of the bucket.
            refill_rate_per_sec: Rate at which tokens are added per second.
        """
        self.capacity = float(capacity)
        self.refill_rate = float(refill_rate_per_sec)
        self.tokens = float(capacity)
        self.last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    def _refill(self) -> None:
        """Calculate and add elapsed tokens up to capacity."""
        # TODO: Calculate elapsed time since self.last_refill
        # Add (elapsed * self.refill_rate) to self.tokens, capped at self.capacity
        # Update self.last_refill
        pass

    async def acquire(self, tokens: float = 1.0) -> float:
        """Wait until `tokens` are available in the bucket, then consume them.

        Args:
            tokens: Number of tokens required for the upcoming request.

        Returns:
            The number of seconds waited (0.0 if tokens were immediately available).
        """
        # TODO: Implement token acquisition with asyncio.Lock
        # 1. Acquire lock
        # 2. Refill tokens
        # 3. If self.tokens >= tokens, decrement self.tokens and return 0.0
        # 4. If insufficient tokens, calculate needed wait time:
        #    wait_seconds = (tokens - self.tokens) / self.refill_rate
        #    Release lock or sleep, then consume and return wait_seconds.
        raise NotImplementedError("TODO: Implement TokenBucket.acquire")


def calculate_decorrelated_jitter(
    base_delay: float,
    max_delay: float,
    previous_delay: float,
) -> float:
    """Calculate next retry backoff using decorrelated jitter.

    Formula: min(max_delay, uniform(base_delay, previous_delay * 3))

    Args:
        base_delay: Minimum backoff floor in seconds.
        max_delay: Maximum backoff ceiling in seconds.
        previous_delay: Delay used in the prior attempt (or base_delay for first retry).

    Returns:
        Calculated sleep time in seconds.
    """
    # TODO: Implement decorrelated jitter formula
    raise NotImplementedError("TODO: Implement calculate_decorrelated_jitter")


async def execute_with_resilience(
    api_call: Callable[[], T],
    rate_limiter: TokenBucket,
    cost_tokens: float = 1.0,
    max_retries: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 8.0,
) -> T:
    """Execute an API call with proactive rate limiting and decorrelated jitter retry.

    Args:
        api_call: Coroutine function or callable that executes the API request.
        rate_limiter: Proactive token bucket limiter.
        cost_tokens: Estimated token cost for this call.
        max_retries: Maximum number of retry attempts on 429 errors.
        base_delay: Base retry backoff.
        max_delay: Maximum retry backoff.

    Returns:
        The successful response from api_call.
    """
    # TODO:
    # 1. Wait for tokens via rate_limiter.acquire(cost_tokens)
    # 2. Try calling api_call()
    # 3. If an exception with status 429 or RateLimitError occurs, retry up to max_retries
    #    using calculate_decorrelated_jitter
    raise NotImplementedError("TODO: Implement execute_with_resilience")

