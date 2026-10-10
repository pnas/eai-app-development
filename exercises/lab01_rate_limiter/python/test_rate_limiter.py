import asyncio
import sys
import time
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parents[3]
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import pytest
from exercises.lab01_rate_limiter.python.solution import (
    TokenBucket,
    calculate_decorrelated_jitter,
    execute_with_resilience,
)


@pytest.mark.asyncio
async def test_token_bucket_initial_burst():
    """Verify that initial burst within capacity completes without delay."""
    bucket = TokenBucket(capacity=5.0, refill_rate_per_sec=1.0)
    start = time.monotonic()
    waited = await bucket.acquire(3.0)
    elapsed = time.monotonic() - start

    assert waited == 0.0
    assert elapsed < 0.05
    assert bucket.tokens == pytest.approx(2.0, rel=0.1)


@pytest.mark.asyncio
async def test_token_bucket_rate_limiting_delays():
    """Verify that requesting more tokens than available forces appropriate wait."""
    bucket = TokenBucket(capacity=2.0, refill_rate_per_sec=10.0)  # 10 tokens/sec = 0.1s per token
    await bucket.acquire(2.0)  # Drain completely

    start = time.monotonic()
    # Need 2 tokens at 10 tokens/sec -> ~0.2 seconds wait
    waited = await bucket.acquire(2.0)
    elapsed = time.monotonic() - start

    assert elapsed >= 0.18
    assert waited >= 0.18


@pytest.mark.asyncio
async def test_concurrent_acquisitions():
    """Verify that multiple concurrent coroutines are serialized without overdrawing."""
    bucket = TokenBucket(capacity=10.0, refill_rate_per_sec=20.0)

    async def worker(worker_id: int):
        await bucket.acquire(1.0)
        return worker_id

    # 15 concurrent workers on 10 capacity bucket
    start = time.monotonic()
    results = await asyncio.gather(*(worker(i) for i in range(15)))
    elapsed = time.monotonic() - start

    assert len(results) == 15
    # First 10 burst immediately, remaining 5 require 5/20 = 0.25s
    assert elapsed >= 0.20


def test_decorrelated_jitter_bounds():
    """Verify decorrelated jitter stays within [base_delay, max_delay]."""
    base = 0.1
    maximum = 2.0
    prev = 0.2

    for _ in range(100):
        jittered = calculate_decorrelated_jitter(base, maximum, prev)
        assert base <= jittered <= maximum
        prev = jittered


class MockRateLimitedApi:
    def __init__(self, failures_before_success: int):
        self.attempts = 0
        self.failures_before_success = failures_before_success

    async def __call__(self):
        self.attempts += 1
        if self.attempts <= self.failures_before_success:
            class MockHttpError(Exception):
                status_code = 429
            raise MockHttpError("HTTP 429 Too Many Requests")
        return {"status": "ok", "attempts": self.attempts}


@pytest.mark.asyncio
async def test_execute_with_resilience_success():
    """Verify resilience wrapper retries on 429 and eventually succeeds."""
    bucket = TokenBucket(capacity=10.0, refill_rate_per_sec=100.0)
    mock_api = MockRateLimitedApi(failures_before_success=2)

    res = await execute_with_resilience(
        mock_api,
        rate_limiter=bucket,
        cost_tokens=1.0,
        max_retries=3,
        base_delay=0.01,
        max_delay=0.1,
    )

    assert res["status"] == "ok"
    assert res["attempts"] == 3
