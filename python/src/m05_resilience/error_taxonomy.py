"""Module 5: Provider HTTP Error Code Taxonomy & Normalized Exceptions.

Normalizes vendor-specific errors (OpenAI, Anthropic, Google Gemini) into
actionable enterprise domain exceptions.

Official References:
- OpenAI Rate Limits: https://developers.openai.com/api/docs/guides/rate-limits
- OpenAI Latency Optimization: https://developers.openai.com/api/docs/guides/latency-optimization
- OpenAI Fast Mode: https://developers.openai.com/api/docs/guides/fast-mode
"""

from __future__ import annotations

import openai
import anthropic
from rich.console import Console

console = Console()


# Base Domain Exceptions
class GenAIError(Exception):
    """Base exception for all GenAI API integration errors."""
    def __init__(self, message: str, retryable: bool = False, status_code: int = 500):
        super().__init__(message)
        self.retryable = retryable
        self.status_code = status_code


class RateLimitExceededError(GenAIError):
    """429: TPM / RPM quota exceeded, or OpenAI 'slow_down' / Fast Mode ramp ceiling."""
    def __init__(self, message: str, retry_after_seconds: float = 5.0, error_code: str = "rate_limit_exceeded"):
        super().__init__(message, retryable=True, status_code=429)
        self.retry_after_seconds = retry_after_seconds
        self.error_code = error_code


class ContextLengthExceededError(GenAIError):
    """400: Prompt exceeds maximum context window of the model."""
    def __init__(self, message: str):
        super().__init__(message, retryable=False, status_code=400)


class ProviderOverloadedError(GenAIError):
    """529 (Anthropic) or 503 (OpenAI server_is_overloaded / resource_unavailable): Provider infrastructure capacity exhausted."""
    def __init__(self, message: str, status_code: int = 503):
        super().__init__(message, retryable=True, status_code=status_code)


class AuthenticationError(GenAIError):
    """401/403: Invalid credentials or forbidden access."""
    def __init__(self, message: str):
        super().__init__(message, retryable=False, status_code=401)


class TransientServerError(GenAIError):
    """500/502/504: Ephemeral gateway or server fault."""
    def __init__(self, message: str):
        super().__init__(message, retryable=True, status_code=500)


def normalize_api_exception(exc: Exception) -> GenAIError:
    """Classify raw SDK exceptions into domain exceptions with retry flags."""
    # Anthropic Exceptions
    if isinstance(exc, anthropic.RateLimitError):
        return RateLimitExceededError(f"Anthropic Rate Limit: {exc.message}")
    if isinstance(exc, anthropic.APIStatusError):
        if exc.status_code == 529:
            return ProviderOverloadedError(f"Anthropic Overloaded (529): {exc.message}", status_code=529)
        if exc.status_code in (401, 403):
            return AuthenticationError(f"Anthropic Auth Failure ({exc.status_code}): {exc.message}")
        if exc.status_code >= 500:
            return TransientServerError(f"Anthropic Server Error ({exc.status_code}): {exc.message}")
        if "context length" in str(exc).lower():
            return ContextLengthExceededError(f"Anthropic Context Exceeded: {exc.message}")

    # OpenAI Exceptions
    if isinstance(exc, openai.RateLimitError):
        msg = str(exc.message)
        code = "slow_down" if "slow_down" in msg else "rate_limit_exceeded"
        retry_after = 5.0
        if hasattr(exc, "response") and exc.response is not None:
            raw_retry = exc.response.headers.get("retry-after")
            if raw_retry:
                try:
                    retry_after = float(raw_retry)
                except ValueError:
                    pass
        return RateLimitExceededError(f"OpenAI Rate Limit ({code}): {msg}", retry_after_seconds=retry_after, error_code=code)
    if isinstance(exc, openai.AuthenticationError):
        return AuthenticationError(f"OpenAI Auth Failure: {exc.message}")
    if isinstance(exc, openai.InternalServerError):
        msg = str(exc.message)
        if "server_is_overloaded" in msg or "resource_unavailable" in msg or getattr(exc, "status_code", 500) == 503:
            return ProviderOverloadedError(f"OpenAI Server Overloaded (503): {msg}", status_code=503)
        return TransientServerError(f"OpenAI Server Error: {exc.message}")
    if isinstance(exc, openai.BadRequestError):
        msg_str = str(exc).lower()
        if "context_length_exceeded" in msg_str or "maximum context length" in msg_str or "max_tokens is too large" in msg_str:
            return ContextLengthExceededError(f"OpenAI Context Window Exceeded: {exc.message}")

    return GenAIError(f"Unhandled API error: {exc}", retryable=False, status_code=500)


def demonstrate_live_taxonomy() -> None:
    """Execute live OpenAI calls and inject errors if 2 attempts succeed without error."""
    console.print("\n[bold cyan]=== Enterprise GenAI Error Taxonomy: Live OpenAI & Error Injection ===[/bold cyan]")
    console.print("[dim]Testing live OpenAI API requests. If >= 2 attempts succeed without error, an error is injected to showcase normalization...[/dim]\n")

    from src.m01_paradigms.client_factory import get_openai_client

    try:
        client = get_openai_client()
    except Exception as e:
        console.print(f"[yellow]⚠️  OpenAI client initialization skipped: {e}[/yellow]")
        return

    live_scenarios = [
        {
            "name": "1. Nominal Request (gpt-4o-mini)",
            "prompt": "Summarize 5G SA network slicing in 10 words.",
            "params": {"max_tokens": 25},
            "force_inject": False,
        },
        {
            "name": "2. Nominal Request #2 (Telecom BGP Diagnostic)",
            "prompt": "State 1 mitigation for BGP route flapping in 10 words.",
            "params": {"max_tokens": 25},
            "force_inject": False,
        },
        {
            "name": "3. Parameter / Context Window Ceiling (max_tokens: 2,000,000)",
            "prompt": "Diagnostic dump",
            "params": {"max_tokens": 2000000},
            "force_inject": False,
        },
        {
            "name": "4. Rate Limit / Transient Overload (Demonstration Injection)",
            "prompt": "Ping UPF node",
            "params": {"max_tokens": 10},
            "force_inject": True,
        },
    ]

    console.print(f"{'Scenario / Provider Call':<46} {'Outcome / Normalized Class':<30} {'Retryable'}")
    console.print("-" * 90)

    consecutive_successes = 0

    for scenario in live_scenarios:
        try:
            # If after 2 attempts we don't get any error from OpenAI, inject an error to showcase normalization
            if scenario.get("force_inject") and consecutive_successes >= 2:
                console.print(f"[magenta]   [Injection] {consecutive_successes} consecutive successful calls observed from OpenAI.[/magenta]")
                console.print("[magenta]   [Injection] Injecting simulated OpenAI RateLimitError (429 TPM quota exceeded) to demonstrate resilience...[/magenta]")
                import httpx
                req = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
                resp = httpx.Response(429, request=req, headers={"retry-after": "6.0"})
                raise openai.RateLimitError(
                    "429 Too Many Requests: Rate limit reached for TPM quota on model gpt-4o-mini (Injected for demonstration)",
                    response=resp,
                    body={"error": {"message": "Rate limit exceeded", "type": "tokens", "code": "rate_limit_exceeded"}},
                )

            res = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": scenario["prompt"]}],
                **scenario["params"],
            )
            consecutive_successes += 1
            content = res.choices[0].message.content or "200 OK"
            clean_text = content.strip().replace("\n", " ")[:28]
            console.print(f"{scenario['name'][:44]:<46} [green]200 OK: \"{clean_text}...\"[/green]")

        except Exception as exc:
            # If it's not a GenAIError yet, normalize it
            normalized = normalize_api_exception(exc)
            retry_str = "[green]YES (Backoff)[/green]" if normalized.retryable else "[red]NO (Fail-Fast)[/red]"
            console.print(f"{scenario['name'][:44]:<46} [bold]{type(normalized).__name__:<30}[/bold] {retry_str}")
            raw_msg = str(exc)[:75].replace("\n", " ")
            console.print(f"[dim]   -> Raw Error: {type(exc).__name__}: {raw_msg}...[/dim]")

    console.print("-" * 90 + "\n")


def main():
    import httpx
    console.print("\n[bold cyan]=== Error Taxonomy & Classification Demonstration ===[/bold cyan]")
    req = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    test_cases = [
        openai.RateLimitError("Rate limit exceeded for token quota", response=httpx.Response(429, request=req), body=None),
        openai.AuthenticationError("Incorrect API key provided: sk-invalid", response=httpx.Response(401, request=req), body=None),
        openai.BadRequestError("This model's maximum context length is 128000 tokens. However, you requested 142000 tokens", response=httpx.Response(400, request=req), body=None),
        anthropic.APIStatusError(message="Anthropic servers are overloaded", response=httpx.Response(529, request=req), body=None),
    ]

    for raw in test_cases:
        norm = normalize_api_exception(raw)
        console.print(f"Raw: [yellow]{type(raw).__name__}[/yellow] --> Normalized: [bold]{type(norm).__name__}[/bold] (Retryable: [green]{norm.retryable}[/green], Status: {norm.status_code})")

    # Run live OpenAI calls with demonstration error injection
    demonstrate_live_taxonomy()


if __name__ == "__main__":
    main()

