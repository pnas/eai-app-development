"""Module 5: Production Circuit Breaker Pattern for LLM Providers.

Protects upstream application latency by failing fast when a provider has
sustained outages or elevated 5xx/429 error rates.
"""

from __future__ import annotations

import enum
import time
from rich.console import Console

console = Console()


class BreakerState(str, enum.Enum):
    CLOSED = "CLOSED"        # Normal operations: calls pass through
    OPEN = "OPEN"            # Tripped: Fast-fails immediately without calling API
    HALF_OPEN = "HALF_OPEN"  # Testing: Allows 1 probe call to check provider recovery


class CircuitBreakerOpenException(Exception):
    """Raised when request is rejected because the circuit breaker is OPEN."""
    pass


class CircuitBreaker:
    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        recovery_timeout_seconds: float = 10.0,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout_seconds = recovery_timeout_seconds

        self.state = BreakerState.CLOSED
        self.failure_count = 0
        self.last_state_change_time = time.time()

    def before_call(self):
        """Evaluate if the call is permitted to proceed."""
        current_time = time.time()

        if self.state == BreakerState.OPEN:
            elapsed = current_time - self.last_state_change_time
            if elapsed >= self.recovery_timeout_seconds:
                self.state = BreakerState.HALF_OPEN
                self.last_state_change_time = current_time
                console.print(f"[yellow][Breaker: {self.name}] Entering HALF_OPEN state (Sending probe request).[/yellow]")
            else:
                raise CircuitBreakerOpenException(
                    f"Circuit breaker '{self.name}' is OPEN. Fast-failing request (cool-off: {self.recovery_timeout_seconds - elapsed:.1f}s remaining)."
                )

    def record_success(self):
        """Called upon successful response."""
        if self.state in (BreakerState.HALF_OPEN, BreakerState.OPEN):
            console.print(f"[bold green][Breaker: {self.name}] Probe succeeded! Resetting breaker to CLOSED state.[/bold green]")
        self.state = BreakerState.CLOSED
        self.failure_count = 0

    def record_failure(self, error: Exception):
        """Called when a call raises a qualifying error."""
        self.failure_count += 1
        console.print(f"[yellow][Breaker: {self.name}] Failure recorded ({self.failure_count}/{self.failure_threshold}): {error}[/yellow]")

        if self.failure_count >= self.failure_threshold:
            self.state = BreakerState.OPEN
            self.last_state_change_time = time.time()
            console.print(f"[bold red][Breaker: {self.name}] Failure threshold reached! Circuit breaker TRIPPED to OPEN.[/bold red]")


def main():
    console.print("\n[bold cyan]=== Circuit Breaker Simulation ===[/bold cyan]")
    breaker = CircuitBreaker("Anthropic_Claude", failure_threshold=3, recovery_timeout_seconds=3.0)

    # Simulate 3 failures
    for i in range(1, 4):
        try:
            breaker.before_call()
            # Simulate failure
            raise ConnectionError("529 Overloaded: Claude capacity exhausted")
        except Exception as e:
            breaker.record_failure(e)

    # Next call should be blocked immediately by circuit breaker
    try:
        console.print("\nAttempting 4th call while breaker is OPEN:")
        breaker.before_call()
    except CircuitBreakerOpenException as cbe:
        console.print(f"[bold red]FAST-FAIL CAUGHT:[/bold red] {cbe}")

    # Wait for cool-off timeout to demonstrate HALF_OPEN probe
    console.print("\nSleeping 3.5s to allow recovery timeout...")
    time.sleep(3.5)

    try:
        breaker.before_call()
        console.print("Probe call permitted. Simulating provider recovery...")
        breaker.record_success()
    except Exception as e:
        console.print(f"Probe failed: {e}")


if __name__ == "__main__":
    main()

