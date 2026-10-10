"""Test suite for Lab 03: Multi-Provider Fallback Cascade with Circuit Breakers."""

import sys
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parents[3]
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import pytest
from exercises.lab03_resilience_cascade.python.solution import (
    CircuitBreaker,
    CircuitState,
    FallbackCascade,
    ProviderTarget,
)


class MockHttpException(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(f"HTTP {status_code}: {message}")
        self.status_code = status_code


def test_primary_success():
    """Verify primary provider serves request when healthy."""
    p1 = ProviderTarget("claude-sonnet", lambda prompt: "Sonnet Response")
    p2 = ProviderTarget("gpt-4o", lambda prompt: "GPT-4o Response")

    cascade = FallbackCascade([p1, p2])
    res = cascade.execute("Hello")

    assert res["served_by"] == "claude-sonnet"
    assert res["result"] == "Sonnet Response"
    assert res["cascade_depth"] == 1


def test_fallback_on_primary_server_error():
    """Verify failover to secondary when primary throws 529 / 500."""
    def p1_caller(prompt):
        raise MockHttpException(529, "Anthropic Overloaded")

    def p2_caller(prompt):
        return "GPT-4o Recovered"

    p1 = ProviderTarget("claude-sonnet", p1_caller)
    p2 = ProviderTarget("gpt-4o", p2_caller)

    cascade = FallbackCascade([p1, p2])
    res = cascade.execute("Hello")

    assert res["served_by"] == "gpt-4o"
    assert res["result"] == "GPT-4o Recovered"
    assert res["cascade_depth"] == 2
    assert p1.breaker.failure_count == 1


def test_circuit_breaker_bypass():
    """Verify that when primary circuit is OPEN, calls bypass primary with zero calls."""
    p1_calls = 0

    def p1_caller(prompt):
        nonlocal p1_calls
        p1_calls += 1
        raise MockHttpException(503, "Service Unavailable")

    p1 = ProviderTarget("claude-sonnet", p1_caller, CircuitBreaker(failure_threshold=2))
    p2 = ProviderTarget("gpt-4o", lambda prompt: "GPT-4o OK")

    cascade = FallbackCascade([p1, p2])

    # First 2 requests trip p1 circuit
    cascade.execute("Req 1")
    cascade.execute("Req 2")
    assert p1.breaker.state == CircuitState.OPEN
    assert p1_calls == 2

    # Third request must BYPASS p1 completely (p1_calls does not increment)
    res = cascade.execute("Req 3")
    assert res["served_by"] == "gpt-4o"
    assert "claude-sonnet" in res["bypassed_providers"]
    assert p1_calls == 2, "Primary caller should not have been invoked when circuit is OPEN"


def test_client_error_400_does_not_fallback():
    """Verify HTTP 400 Bad Request fails immediately without falling back."""
    p2_invoked = False

    def p1_caller(prompt):
        raise MockHttpException(400, "Bad Request: Invalid JSON Schema")

    def p2_caller(prompt):
        nonlocal p2_invoked
        p2_invoked = True
        return "Should never run"

    p1 = ProviderTarget("claude-sonnet", p1_caller)
    p2 = ProviderTarget("gpt-4o", p2_caller)

    cascade = FallbackCascade([p1, p2])

    with pytest.raises(MockHttpException) as exc_info:
        cascade.execute("Bad prompt")

    assert exc_info.value.status_code == 400
    assert p2_invoked is False, "Secondary provider should NOT be called on client 400 error"


def test_all_providers_exhausted():
    """Verify RuntimeError is raised when all cascade options fail."""
    p1 = ProviderTarget("claude", lambda p: (_ for _ in ()).throw(MockHttpException(500, "Fail 1")))
    p2 = ProviderTarget("gpt", lambda p: (_ for _ in ()).throw(MockHttpException(500, "Fail 2")))

    cascade = FallbackCascade([p1, p2])
    with pytest.raises(RuntimeError) as exc_info:
        cascade.execute("Prompt")

    assert "All providers exhausted" in str(exc_info.value)

