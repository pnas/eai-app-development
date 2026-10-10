"""Module 1: Streaming Comparison & SSE Chunk Mechanics.

Demonstrates consuming Server-Sent Events (SSE) streams and capturing
usage metadata chunks across OpenAI, Anthropic, and Google Gemini.
"""

from __future__ import annotations

import sys
from rich.console import Console
from google.genai import types as gemini_types
from src.m01_paradigms.client_factory import (
    get_openai_client,
    get_anthropic_client,
    get_gemini_client,
)

console = Console()


def stream_openai(prompt: str):
    """Stream response from OpenAI and capture usage."""
    console.print("\n[bold cyan]=== Streaming OpenAI (gpt-4o-mini) ===[/bold cyan]")
    client = get_openai_client()

    # Note stream_options: {"include_usage": True} is essential to receive usage in the final chunk!
    stream = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        stream=True,
        stream_options={"include_usage": True},
    )

    usage = None
    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            sys.stdout.write(chunk.choices[0].delta.content)
            sys.stdout.flush()
        if chunk.usage:
            usage = chunk.usage

    print()
    if usage:
        console.print(
            f"[dim]Usage: Input={usage.prompt_tokens}, Output={usage.completion_tokens}, Total={usage.total_tokens}[/dim]"
        )


def stream_anthropic(prompt: str):
    """Stream response from Anthropic Claude using typed event stream."""
    console.print("\n[bold magenta]=== Streaming Anthropic (claude-3-5-haiku) ===[/bold magenta]")
    client = get_anthropic_client()

    with client.messages.stream(
        model="claude-3-5-haiku-20241022",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        for text in stream.text_stream:
            sys.stdout.write(text)
            sys.stdout.flush()

        response = stream.get_final_message()

    print()
    console.print(
        f"[dim]Usage: Input={response.usage.input_tokens}, Output={response.usage.output_tokens}[/dim]"
    )


def stream_gemini(prompt: str):
    """Stream response from Google Gemini."""
    console.print("\n[bold green]=== Streaming Google Gemini (gemini-1.5-flash) ===[/bold green]")
    client = get_gemini_client()

    response = client.models.generate_content_stream(
        model="gemini-1.5-flash",
        contents=prompt,
    )

    usage = None
    for chunk in response:
        if chunk.text:
            sys.stdout.write(chunk.text)
            sys.stdout.flush()
        if chunk.usage_metadata:
            usage = chunk.usage_metadata

    print()
    if usage:
        console.print(
            f"[dim]Usage: Input={usage.prompt_token_count}, Output={usage.candidates_token_count}[/dim]"
        )


def main():
    prompt = "In 2 sentences, explain why streaming reduces Time-To-First-Token (TTFT) for users."
    try:
        stream_openai(prompt)
    except Exception as e:
        console.print(f"[red]OpenAI error: {e}[/red]")

    try:
        stream_anthropic(prompt)
    except Exception as e:
        console.print(f"[red]Anthropic error: {e}[/red]")

    try:
        stream_gemini(prompt)
    except Exception as e:
        console.print(f"[red]Gemini error: {e}[/red]")


if __name__ == "__main__":
    main()

