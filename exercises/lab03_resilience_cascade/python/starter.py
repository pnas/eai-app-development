"""Lab 03 Starter: Multi-Provider Fallback Cascade with Circuit Breakers."""

from __future__ import annotations

import enum
import time
from typing import Any, Callable, Dict, List, Optional


class CircuitState(enum.Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    """Per-provider circuit breaker."""

    def __init__(self, failure_threshold: int = 3, recovery_timeout_sec: float = 30.0) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout_sec = recovery_timeout_sec
        self.failure_count = 0
        self.state = CircuitState.CLOSED
        self.last_state_change = time.monotonic()

    def allow_request(self) -> bool:
        """Check if request is permitted through the circuit."""
        now = time.monotonic()
        if self.state == CircuitState.OPEN:
            if now - self.last_state_change > self.recovery_timeout_sec:
                self.state = CircuitState.HALF_OPEN
                self.last_state_change = now
                return True
            return False
        return True

    def record_success(self) -> None:
        self.failure_count = 0
        self.state = CircuitState.CLOSED

    def record_failure(self) -> None:
        self.failure_count += 1
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            self.last_state_change = time.monotonic()


class ProviderTarget:
    def __init__(
        self,
        name: str,
        caller: Callable[[str], Any],
        circuit_breaker: Optional[CircuitBreaker] = None,
    ) -> None:
        self.name = name
        self.caller = caller
        self.breaker = circuit_breaker or CircuitBreaker()


class FallbackCascade:
    """Cascading orchestrator across primary, secondary, and tertiary providers."""

    def __init__(self, providers: List[ProviderTarget]) -> None:
        self.providers = providers

    def execute(self, prompt: str) -> Dict[str, Any]:
        """Execute request across providers in cascade sequence.

        Requirements:
        1. Iterate through self.providers in order.
        2. Check provider.breaker.allow_request(). If False, bypass immediately.
        3. Try invoking provider.caller(prompt).
        4. On success:
           - Record success in provider breaker.
           - Return dict: {"served_by": provider.name, "result": result, "cascade_depth": attempt_index}
        5. On exception:
           - If status_code is 400 (Client Error), DO NOT fallback; raise exception immediately!
           - If transient error (5xx, 429, etc.), record failure in provider breaker and continue to next provider.
        6. If all providers are exhausted or circuit-broken, raise RuntimeError("All providers unavailable").
        """
        # TODO: Implement multi-provider cascading fallback logic
        raise NotImplementedError("TODO: Implement FallbackCascade.execute")

