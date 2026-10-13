"""Module 1: Side-by-side Chat Completion Comparison.

Demonstrates normalized message schemas, roles, reasoning tokens accounting,
and token usage across OpenAI, Anthropic, and Google Gemini.

Official References:
- Anthropic Working with Messages: https://platform.claude.com/docs/en/build-with-claude/working-with-messages
- Anthropic Effort Controls: https://platform.claude.com/docs/en/build-with-claude/effort
- Anthropic Streaming: https://platform.claude.com/docs/en/build-with-claude/streaming
- OpenAI Chat Completions API: https://platform.openai.com/docs/api-reference/chat
- Google GenAI SDK: https://googleapis.github.io/python-genai/
- Google Gemini Models: https://ai.google.dev/gemini-api/docs/models
- Google Gemini Streaming: https://ai.google.dev/gemini-api/docs/streaming
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from rich.console import Console
from rich.table import Table

from google.genai import types as gemini_types
from src.m01_paradigms.client_factory import (
    get_openai_client,
    get_anthropic_client,
    get_gemini_client,
)

console = Console()


@dataclass
class NormalizedResponse:
    provider: str
    model: str
    content: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    finish_reason: str
    reasoning_tokens: Optional[int] = 0


def call_openai(prompt: str, system_prompt: str) -> NormalizedResponse:
    """Execute completion via OpenAI SDK."""
    client = get_openai_client()
    model = "gpt-4o-mini"

    # OpenAI format: Developer/System role + User role in messages array
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "developer", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )

    choice = response.choices[0]
    usage = response.usage
    reasoning_tok = 0
    if usage and getattr(usage, "completion_tokens_details", None):
        reasoning_tok = getattr(usage.completion_tokens_details, "reasoning_tokens", 0) or 0

    return NormalizedResponse(
        provider="OpenAI",
        model=model,
        content=choice.message.content or "",
        prompt_tokens=usage.prompt_tokens if usage else 0,
        completion_tokens=usage.completion_tokens if usage else 0,
        total_tokens=usage.total_tokens if usage else 0,
        finish_reason=choice.finish_reason,
        reasoning_tokens=reasoning_tok,
    )


def call_anthropic(prompt: str, system_prompt: str) -> NormalizedResponse:
    """Execute completion via Anthropic SDK.
    
    NOTE: Claude 4.7+ and Claude 5.x do NOT accept temperature, top_p, or top_k
    (passing them causes HTTP 400). Sampling is steered via prompt or output_config.effort.
    """
    client = get_anthropic_client()
    model = "claude-haiku-5-5"

    # Anthropic format: Top-level system param; messages array with user/assistant
    # Effort controls reasoning depth (low, medium, high, xhigh, max)
    response = client.messages.create(
        model=model,
        system=system_prompt,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
        output_config={"effort": "medium"},
    )

    content_text = ""
    reasoning_tok = 0
    for block in response.content:
        if block.type == "text":
            content_text += block.text
        elif block.type == "thinking":
            # Count thinking block characters/tokens if available
            reasoning_tok += len(getattr(block, "thinking", "").split())

    return NormalizedResponse(
        provider="Anthropic",
        model=model,
        content=content_text,
        prompt_tokens=response.usage.input_tokens,
        completion_tokens=response.usage.output_tokens,
        total_tokens=response.usage.input_tokens + response.usage.output_tokens,
        finish_reason=response.stop_reason or "unknown",
        reasoning_tokens=reasoning_tok,
    )


def call_gemini(prompt: str, system_prompt: str) -> NormalizedResponse:
    """Execute completion via Google Gemini SDK."""
    client = get_gemini_client()
    model = "gemini-3.8-flash"

    # Gemini format: system_instruction config, contents list
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=gemini_types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.2,
        ),
    )

    prompt_tok = response.usage_metadata.prompt_token_count if response.usage_metadata else 0
    comp_tok = response.usage_metadata.candidates_token_count if response.usage_metadata else 0

    return NormalizedResponse(
        provider="Google Gemini",
        model=model,
        content=response.text or "",
        prompt_tokens=prompt_tok,
        completion_tokens=comp_tok,
        total_tokens=prompt_tok + comp_tok,
        finish_reason="stop",
        reasoning_tokens=0,
    )


def main():
    system = "You are a cloud architecture expert. Answer in 2 succinct bullet points."
    query = "What are the primary differences between REST and gRPC in distributed microservices?"

    table = Table(title="Cross-Provider API Execution Benchmark")
    table.add_column("Provider", style="cyan", no_wrap=True)
    table.add_column("Model", style="magenta")
    table.add_column("Input Tok", justify="right", style="green")
    table.add_column("Output Tok", justify="right", style="green")
    table.add_column("Reasoning Tok", justify="right", style="cyan")
    table.add_column("Total Tok", justify="right", style="bold green")
    table.add_column("Content Snippet", style="white")

    providers = [
        ("OpenAI", call_openai),
        ("Anthropic", call_anthropic),
        ("Google Gemini", call_gemini),
    ]

    for name, caller in providers:
        try:
            res = caller(query, system)
            snippet = res.content.replace("\n", " ")[:65] + "..."
            table.add_row(
                res.provider,
                res.model,
                str(res.prompt_tokens),
                str(res.completion_tokens),
                str(res.reasoning_tokens or 0),
                str(res.total_tokens),
                snippet,
            )
        except Exception as e:
            table.add_row(name, "error", "-", "-", "-", "-", f"[red]{type(e).__name__}: {e}[/red]")

    console.print(table)


if __name__ == "__main__":
    main()

