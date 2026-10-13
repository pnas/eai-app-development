"""Module 1: Streaming Comparison & SSE Chunk Mechanics.

Demonstrates consuming Server-Sent Events (SSE) streams and capturing
usage metadata chunks across OpenAI, Anthropic, and Google Gemini
(including Gemini GenerateContentStream and the new Interactions API).

Official References:
- Anthropic Streaming: https://platform.claude.com/docs/en/build-with-claude/streaming
- Anthropic Working with Messages: https://platform.claude.com/docs/en/build-with-claude/working-with-messages
- Anthropic Effort Controls: https://platform.claude.com/docs/en/build-with-claude/effort
- OpenAI Streaming & SSE: https://platform.openai.com/docs/api-reference/chat/streaming
- Google Gemini Models: https://ai.google.dev/gemini-api/docs/models
- Google Gemini Streaming: https://ai.google.dev/gemini-api/docs/streaming
- Google Gemini Interactions API: https://ai.google.dev/gemini-api/docs/interactions-overview
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
    """Stream response from Anthropic Claude using typed event stream.
    
    Claude 5.5 / 5.x emits typed SSE deltas:
    - `thinking_delta`: intermediate chain-of-thought tokens
    - `signature_delta`: cryptographic verification signature for thinking
    - `text_delta`: visible answer content
    """
    console.print("\n[bold magenta]=== Streaming Anthropic (claude-haiku-5-5) ===[/bold magenta]")
    client = get_anthropic_client()

    with client.messages.stream(
        model="claude-haiku-5-5",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
        output_config={"effort": "medium"},
    ) as stream:
        for event in stream:
            if hasattr(event, "type") and event.type == "content_block_delta":
                delta = event.delta
                delta_type = getattr(delta, "type", "")
                if delta_type == "text_delta":
                    sys.stdout.write(delta.text)
                    sys.stdout.flush()
                elif delta_type == "thinking_delta":
                    sys.stdout.write(f"[thinking: {delta.thinking}]")
                    sys.stdout.flush()
                elif delta_type == "signature_delta":
                    sys.stdout.write("[sig]")
                    sys.stdout.flush()
            elif hasattr(event, "type") and event.type == "text":
                sys.stdout.write(event.text)
                sys.stdout.flush()

        response = stream.get_final_message()

    print()
    console.print(
        f"[dim]Usage: Input={response.usage.input_tokens}, Output={response.usage.output_tokens}[/dim]"
    )


def stream_gemini(prompt: str):
    """Stream response from Google Gemini via generate_content_stream."""
    console.print("\n[bold green]=== Streaming Google Gemini Content (gemini-3.8-flash) ===[/bold green]")
    client = get_gemini_client()

    response = client.models.generate_content_stream(
        model="gemini-3.8-flash",
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


def stream_gemini_interactions(prompt: str):
    """Stream response from Google Gemini via the new Interactions API with event-stream handling."""
    console.print("\n[bold green]=== Streaming Google Gemini Interactions API (gemini-3.8-flash) ===[/bold green]")
    client = get_gemini_client()

    stream = client.interactions.create(
        model="gemini-3.8-flash",
        input=prompt,
        generation_config={"thinking_summaries": "auto"},
        stream=True,
    )

    for event in stream:
        if event.event_type == "step.start":
            step_type = getattr(event.step, "type", "step")
            if step_type == "thought":
                console.print("[dim italic][Thought Summary][/dim italic] ", end="")
        elif event.event_type == "step.delta":
            delta = event.delta
            delta_type = getattr(delta, "type", None)
            if delta_type == "thought_summary":
                content = getattr(delta, "content", None)
                if content and getattr(content, "text", None):
                    sys.stdout.write(content.text)
                    sys.stdout.flush()
            elif delta_type == "text" or hasattr(delta, "text"):
                text = getattr(delta, "text", "")
                if text:
                    sys.stdout.write(text)
                    sys.stdout.flush()

    print()


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
        console.print(f"[red]Gemini Content Stream error: {e}[/red]")

    try:
        stream_gemini_interactions(prompt)
    except Exception as e:
        console.print(f"[red]Gemini Interactions Stream error: {e}[/red]")


if __name__ == "__main__":
    main()

