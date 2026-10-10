"""Module 5: Provider HTTP Error Code Taxonomy & Normalized Exceptions.

Normalizes vendor-specific errors (OpenAI, Anthropic, Google Gemini) into
actionable enterprise domain exceptions.
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
    """429: TPM / RPM quota exceeded."""
    def __init__(self, message: str, retry_after_seconds: float = 5.0):
        super().__init__(message, retryable=True, status_code=429)
        self.retry_after_seconds = retry_after_seconds


class ContextLengthExceededError(GenAIError):
    """400: Prompt exceeds maximum context window of the model."""
    def __init__(self, message: str):
        super().__init__(message, retryable=False, status_code=400)


class ProviderOverloadedError(GenAIError):
    """529 (Anthropic) or 503: Provider infrastructure capacity exhausted."""
    def __init__(self, message: str):
        super().__init__(message, retryable=True, status_code=529)


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
            return ProviderOverloadedError(f"Anthropic Overloaded (529): {exc.message}")
        if exc.status_code in (401, 403):
            return AuthenticationError(f"Anthropic Auth Failure ({exc.status_code}): {exc.message}")
        if exc.status_code >= 500:
            return TransientServerError(f"Anthropic Server Error ({exc.status_code}): {exc.message}")
        if "context length" in str(exc).lower():
            return ContextLengthExceededError(f"Anthropic Context Exceeded: {exc.message}")

    # OpenAI Exceptions
    if isinstance(exc, openai.RateLimitError):
        return RateLimitExceededError(f"OpenAI Rate Limit: {exc.message}")
    if isinstance(exc, openai.AuthenticationError):
        return AuthenticationError(f"OpenAI Auth Failure: {exc.message}")
    if isinstance(exc, openai.InternalServerError):
        return TransientServerError(f"OpenAI Server Error: {exc.message}")
    if isinstance(exc, openai.BadRequestError):
        if "context_length_exceeded" in str(exc) or "maximum context length" in str(exc):
            return ContextLengthExceededError(f"OpenAI Context Window Exceeded: {exc.message}")

    return GenAIError(f"Unhandled API error: {exc}", retryable=False, status_code=500)


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


if __name__ == "__main__":
    main()
