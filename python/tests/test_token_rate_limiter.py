"""Tests for Enterprise LLM Token Rate Limiter and Governor (WSO2 Pattern)."""

import time
import pytest
from src.m05_resilience.token_rate_limiter import (
    TokenAwareRateLimiter,
    TierPolicy,
    RateLimitHeaders,
)
from src.langchain_suite.m05_resilience.rate_limited_chain import (
    LangChainTokenRateLimiter,
    RateLimitedMockModel,
    BackupMockModel,
    RateLimitExceededError,
)
from langchain_core.messages import HumanMessage


def test_token_limiter_prompt_ceiling():
    policy = TierPolicy(
        tier_name="Test-Tier",
        max_prompt_tokens=1000,
        max_completion_tokens=500,
        total_token_capacity=5000.0,
        refill_rate_tokens_per_sec=500.0,
        max_budget_usd=10.0,
    )
    limiter = TokenAwareRateLimiter(policy)

    allowed, headers, reason = limiter.acquire(prompt_tokens=1500, estimated_completion_tokens=100)
    assert not allowed
    assert "Prompt tokens (1500) exceeded maximum allowed" in reason


def test_token_limiter_completion_ceiling():
    policy = TierPolicy(
        tier_name="Test-Tier",
        max_prompt_tokens=1000,
        max_completion_tokens=500,
        total_token_capacity=5000.0,
        refill_rate_tokens_per_sec=500.0,
        max_budget_usd=10.0,
    )
    limiter = TokenAwareRateLimiter(policy)

    allowed, headers, reason = limiter.acquire(prompt_tokens=200, estimated_completion_tokens=800)
    assert not allowed
    assert "Estimated completion tokens (800) exceeded ceiling" in reason


def test_token_limiter_bucket_exhaustion_and_headers():
    policy = TierPolicy(
        tier_name="Test-Tier",
        max_prompt_tokens=2000,
        max_completion_tokens=1000,
        total_token_capacity=1000.0,
        refill_rate_tokens_per_sec=100.0,
        max_budget_usd=10.0,
    )
    limiter = TokenAwareRateLimiter(policy)

    # First request: 700 tokens -> succeeds
    allowed, headers, _ = limiter.acquire(500, 200)
    assert allowed
    assert headers.remaining_tokens == 300

    # Second request: 500 tokens -> exceeds remaining 300 tokens
    allowed2, headers2, reason2 = limiter.acquire(300, 200)
    assert not allowed2
    assert "HTTP 429 Too Many Requests" in reason2
    h_dict = headers2.to_dict()
    assert "Retry-After" in h_dict
    assert int(h_dict["Retry-After"]) >= 1


def test_token_limiter_budget_exceeded():
    policy = TierPolicy(
        tier_name="Micro-Tier",
        max_prompt_tokens=2000,
        max_completion_tokens=1000,
        total_token_capacity=10000.0,
        refill_rate_tokens_per_sec=1000.0,
        max_budget_usd=0.0001,  # Ultra-low budget
        cost_per_million_tokens=1.0,
    )
    limiter = TokenAwareRateLimiter(policy)

    # Consumes 500 tokens = $0.0005 > $0.0001
    allowed, headers, reason = limiter.acquire(400, 100)
    assert not allowed
    assert "BudgetExceeded" in reason


def test_langchain_governor_fallback_cascade():
    governor = LangChainTokenRateLimiter(
        max_prompt_tokens=1000,
        max_completion_tokens=500,
        capacity_tokens=800.0,
        refill_rate_per_sec=10.0,
    )
    primary = RateLimitedMockModel(model_name="primary", governor=governor)
    backup = BackupMockModel(model_name="backup")

    resilient_chain = primary.with_fallbacks([backup])

    # First small call passes primary
    res1 = resilient_chain.invoke([HumanMessage(content="Hello")])
    assert "primary" in res1.response_metadata["model"]

    # Over max prompt tokens on governor directly raises ValueError
    with pytest.raises(ValueError, match="PayloadRejected"):
        governor.check_and_consume(estimated_prompt_tokens=1500)

    # Drain remaining tokens to force 429
    governor.current_tokens = 50.0  # Force deficit
    res2 = resilient_chain.invoke([HumanMessage(content="Normal size prompt for failover test")])
    assert "backup" in res2.response_metadata["model"]
    assert res2.response_metadata["failover_reason"] == "429_RATE_LIMIT"


def test_token_limiter_reconcile_usage():
    policy = TierPolicy(
        tier_name="Reconcile-Tier",
        max_prompt_tokens=2000,
        max_completion_tokens=1000,
        total_token_capacity=5000.0,
        refill_rate_tokens_per_sec=0.0,  # freeze refill for clean token math
        max_budget_usd=10.0,
        cost_per_million_tokens=1.0,
    )
    limiter = TokenAwareRateLimiter(policy)

    # Initial capacity: 5000 tokens
    # Acquire with estimate: 600 total (400 prompt + 200 completion)
    allowed, headers, _ = limiter.acquire(400, 200)
    assert allowed
    assert limiter.current_tokens == 4400.0

    # Actual usage was only 350 tokens (refund 250 tokens)
    limiter.reconcile_usage(reserved_total_tokens=600, actual_prompt_tokens=300, actual_completion_tokens=50)
    assert limiter.current_tokens == 4650.0

    # Actual usage was higher: estimate 500, actual 700 (debit 200 tokens)
    limiter.reconcile_usage(reserved_total_tokens=500, actual_prompt_tokens=400, actual_completion_tokens=300)
    assert limiter.current_tokens == 4450.0


def test_openai_rate_limited_executor_preflight_rejection():
    from src.m05_resilience.token_rate_limiter import OpenAIRateLimitedExecutor
    policy = TierPolicy(
        tier_name="Test-Preflight",
        max_prompt_tokens=50,
        max_completion_tokens=50,
        total_token_capacity=1000.0,
        refill_rate_tokens_per_sec=100.0,
        max_budget_usd=1.0,
    )
    limiter = TokenAwareRateLimiter(policy)
    executor = OpenAIRateLimitedExecutor(limiter=limiter, client=None)

    # Long prompt exceeding max_prompt_tokens
    long_prompt = "Tell me everything about telecommunications and 5G network slicing " * 10
    result = executor.execute(
        scenario_name="Ceiling Breach Test",
        prompt=long_prompt,
        max_completion_tokens=20,
    )
    assert not result.allowed
    assert result.status_code == 400
    assert "PayloadRejected" in result.reason
    assert result.response_text is None


