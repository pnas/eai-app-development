"""Module 5: Production Circuit Breaker Pattern for LLM Providers.

Protects upstream application latency by failing fast when a provider has
sustained outages or elevated 5xx/429 error rates.
Integrates live model API callers for Anthropic Claude, OpenAI GPT, and Google Gemini.
"""

from __future__ import annotations

import enum
import os
import time
from typing import Callable, TypeVar
from rich.console import Console

from src.m01_paradigms.client_factory import (
    get_anthropic_client,
    get_openai_client,
    get_gemini_client,
)

console = Console()
T = TypeVar("T")


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
        recovery_timeout_seconds: float = 5.0,
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

    def execute(self, fn: Callable[[], T]) -> T:
        """Executes a callable through the circuit breaker lifecycle."""
        self.before_call()
        try:
            result = fn()
            self.record_success()
            return result
        except Exception as e:
            self.record_failure(e)
            raise e


# ---------------------------------------------------------
# Live Model Callers (Anthropic, OpenAI, Google Gemini)
# ---------------------------------------------------------

def call_anthropic_model(prompt: str) -> str:
    if not os.getenv("ANTHROPIC_API_KEY"):
        return f"[Mock Anthropic Claude] Handled query: '{prompt}'. Status: Healthy."
    client = get_anthropic_client()
    try:
        res = client.messages.create(
            model="claude-haiku-5-5",
            max_tokens=60,
            messages=[{"role": "user", "content": prompt}],
        )
        for block in res.content:
            if hasattr(block, "text"):
                return block.text
        return ""
    except Exception:
        res = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=60,
            messages=[{"role": "user", "content": prompt}],
        )
        for block in res.content:
            if hasattr(block, "text"):
                return block.text
        return ""


def call_openai_model(prompt: str) -> str:
    if not os.getenv("OPENAI_API_KEY"):
        return f"[Mock OpenAI GPT] Handled query: '{prompt}'. Status: Healthy."
    client = get_openai_client()
    try:
        res = client.chat.completions.create(
            model="gpt-4.1-mini",
            max_tokens=60,
            messages=[{"role": "user", "content": prompt}],
        )
        return res.choices[0].message.content or ""
    except Exception:
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=60,
            messages=[{"role": "user", "content": prompt}],
        )
        return res.choices[0].message.content or ""


def call_gemini_model(prompt: str) -> str:
    if not os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
        return f"[Mock Google Gemini] Handled query: '{prompt}'. Status: Healthy."
    client = get_gemini_client()
    try:
        res = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=prompt,
        )
        return res.text or ""
    except Exception:
        res = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        return res.text or ""


def main():
    console.print("\n[bold cyan]=== Production Circuit Breaker with Frontier Models (Python) ===[/bold cyan]")

    anthropic_breaker = CircuitBreaker("Anthropic_Claude", failure_threshold=3, recovery_timeout_seconds=2.5)
    openai_breaker = CircuitBreaker("OpenAI_GPT", failure_threshold=3, recovery_timeout_seconds=2.5)
    gemini_breaker = CircuitBreaker("Google_Gemini", failure_threshold=3, recovery_timeout_seconds=2.5)

    test_prompt = "In 10 words or less, what is the role of 5G Standalone core?"

    # Phase 1: Real Model Invocations via Circuit Breakers
    console.print("[cyan]Phase 1: Executing Live Model Calls Protected by Circuit Breakers (CLOSED state)...[/cyan]")

    try:
        res_ant = anthropic_breaker.execute(lambda: call_anthropic_model(test_prompt))
        console.print(f"[green][OK] Anthropic Breaker [{anthropic_breaker.state.value}]:[/green] {res_ant.strip()}")
    except Exception as e:
        console.print(f"[yellow]Anthropic call note: {e}[/yellow]")

    try:
        res_oai = openai_breaker.execute(lambda: call_openai_model(test_prompt))
        console.print(f"[green][OK] OpenAI Breaker [{openai_breaker.state.value}]:[/green] {res_oai.strip()}")
    except Exception as e:
        console.print(f"[yellow]OpenAI call note: {e}[/yellow]")

    try:
        res_gem = gemini_breaker.execute(lambda: call_gemini_model(test_prompt))
        console.print(f"[green][OK] Gemini Breaker [{gemini_breaker.state.value}]:[/green] {res_gem.strip()}")
    except Exception as e:
        console.print(f"[yellow]Gemini call note: {e}[/yellow]")

    # Phase 2: Fault Injection & Trip Anthropic Breaker to OPEN
    console.print("\n[cyan]Phase 2: Inducing Consecutive 529/429 Outages on Anthropic to Trigger Circuit Breaker...[/cyan]")
    for i in range(1, 4):
        try:
            def failing_call():
                raise ConnectionError(f"HTTP 529 Overloaded: Claude infrastructure capacity reached (attempt {i})")
            anthropic_breaker.execute(failing_call)
        except Exception:
            pass

    # Phase 3: Fast-Fail Verification (0ms overhead)
    console.print("\n[cyan]Phase 3: Fast-Fail Verification when Circuit is OPEN:[/cyan]")
    start_time = time.perf_counter()
    try:
        anthropic_breaker.execute(lambda: call_anthropic_model("Test prompt during outage"))
    except CircuitBreakerOpenException as cbe:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        console.print(f"[red][OK] FAST-FAIL CAUGHT in {elapsed_ms:.2f}ms (0 network calls made):[/red] {cbe}")

    # Phase 4: Cool-off, Transition to HALF_OPEN & Probe Recovery
    console.print("\n[cyan]Phase 4: Waiting for cool-off timeout (2.6s) to allow HALF_OPEN probe...[/cyan]")
    time.sleep(2.6)

    try:
        console.print("[yellow]Sending probe request to real Anthropic model to test recovery...[/yellow]")
        probe_res = anthropic_breaker.execute(lambda: call_anthropic_model("Ping recovery test"))
        console.print(f"[green][OK] Probe succeeded! Response:[/green] {probe_res.strip()}")
        console.print(f"[green][OK] Breaker state successfully recovered to: {anthropic_breaker.state.value}[/green]")
    except Exception as e:
        console.print(f"[red]Probe failed: {e}[/red]")

    # Phase 5: Resilient Router Demonstration
    console.print("\n[cyan]Phase 5: Resilient Router cascading across Breaker-Protected Models:[/cyan]")
    # Intentionally trip Anthropic again
    for _ in range(3):
        anthropic_breaker.record_failure(ConnectionError("Simulated transient outage"))

    providers = [
        {"name": "Anthropic", "breaker": anthropic_breaker, "caller": lambda: call_anthropic_model("What is eNodeB?")},
        {"name": "OpenAI", "breaker": openai_breaker, "caller": lambda: call_openai_model("What is eNodeB?")},
        {"name": "Gemini", "breaker": gemini_breaker, "caller": lambda: call_gemini_model("What is eNodeB?")},
    ]

    routed_result = None
    used_provider = None

    for p in providers:
        try:
            console.print(f"[dim]Checking {p['name']} circuit (state: {p['breaker'].state.value})...[/dim]")
            routed_result = p["breaker"].execute(p["caller"])
            used_provider = p["name"]
            break
        except CircuitBreakerOpenException:
            console.print(f"[yellow][ROUTER] {p['name']} circuit is OPEN. Fast-failing to next healthy provider.[/yellow]")
        except Exception as e:
            console.print(f"[red][ROUTER] {p['name']} failed: {e}[/red]")

    console.print(f"\n[bold green][OK] Resilient Routing Successful! Answer served by healthy provider [{used_provider}]:[/bold green]\n{routed_result.strip() if routed_result else ''}\n")


if __name__ == "__main__":
    main()
