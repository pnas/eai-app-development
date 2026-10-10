"""Lab 03 Reference Solution: Multi-Provider Fallback Cascade with Circuit Breakers."""

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
        """Execute request across providers in cascade sequence."""
        errors_collected: List[str] = []

        for idx, provider in enumerate(self.providers):
            # 1. Circuit breaker gate check
            if not provider.breaker.allow_request():
                errors_collected.append(f"{provider.name}: Circuit OPEN (bypassed)")
                continue

            # 2. Invoke provider
            try:
                result = provider.caller(prompt)
                provider.breaker.record_success()
                return {
                    "served_by": provider.name,
                    "result": result,
                    "cascade_depth": idx + 1,
                    "bypassed_providers": [
                        p.name for p in self.providers[:idx] if p.breaker.state == CircuitState.OPEN
                    ],
                }
            except Exception as exc:
                # 3. Check for 400 Bad Request
                status_code = getattr(exc, "status_code", getattr(exc, "status", None))
                if status_code == 400 or "400" in str(exc):
                    # Client errors are unrecoverable by switching provider; raise immediately
                    raise exc

                # 4. Record transient server failure in circuit breaker
                provider.breaker.record_failure()
                errors_collected.append(f"{provider.name}: {exc}")

        # 5. All providers exhausted
        raise RuntimeError(f"All providers exhausted in cascade. Errors: {'; '.join(errors_collected)}")

