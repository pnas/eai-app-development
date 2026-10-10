"""Module 1: Tool & Function Calling Protocols.

Demonstrates declaring tools, forcing tool execution, and handling tool responses
across OpenAI, Anthropic, and Google Gemini wire formats.
"""

from __future__ import annotations

import json
from rich.console import Console
from google.genai import types as gemini_types
from src.m01_paradigms.client_factory import (
    get_openai_client,
    get_anthropic_client,
    get_gemini_client,
)

console = Console()


# Concrete implementation of tool
def get_service_health(service_name: str, environment: str = "production") -> dict:
    """Mock health check status for a service."""
    return {
        "service": service_name,
        "environment": environment,
        "status": "HEALTHY",
        "latency_ms": 24.5,
        "active_replicas": 5,
    }


def demo_openai_tool_call():
    console.print("\n[bold cyan]=== OpenAI Tool Calling Wire Protocol ===[/bold cyan]")
    client = get_openai_client()

    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_service_health",
                "description": "Get real-time operational health metrics for an internal service.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "service_name": {"type": "string", "description": "e.g. auth-service, billing"},
                        "environment": {"type": "string", "enum": ["staging", "production"]},
                    },
                    "required": ["service_name"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
        }
    ]

    messages = [{"role": "user", "content": "Is the billing service healthy in production?"}]

    # Step 1: Model decides to call tool
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        tools=tools,
        tool_choice="auto",
    )

    msg = response.choices[0].message
    if msg.tool_calls:
        tool_call = msg.tool_calls[0]
        func_name = tool_call.function.name
        args = json.loads(tool_call.function.arguments)
        console.print(f"[green]OpenAI called tool:[/green] {func_name} with {args}")

        # Step 2: Execute tool locally
        tool_result = get_service_health(**args)

        # Step 3: Append assistant message + tool result message to history
        messages.append(msg)
        messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(tool_result),
            }
        )

        final_response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
        )
        console.print(f"[bold]Final Answer:[/bold] {final_response.choices[0].message.content}")


def demo_anthropic_tool_call():
    console.print("\n[bold magenta]=== Anthropic Tool Calling Wire Protocol ===[/bold magenta]")
    client = get_anthropic_client()

    tools = [
        {
            "name": "get_service_health",
            "description": "Get real-time operational health metrics for an internal service.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "service_name": {"type": "string", "description": "e.g. auth-service, billing"},
                    "environment": {"type": "string", "enum": ["staging", "production"]},
                },
                "required": ["service_name"],
            },
        }
    ]

    messages = [{"role": "user", "content": "Check health of auth-service in production."}]

    response = client.messages.create(
        model="claude-3-5-haiku-20241022",
        max_tokens=1024,
        tools=tools,
        messages=messages,
    )

    tool_use_block = next((b for b in response.content if b.type == "tool_use"), None)
    if tool_use_block:
        console.print(f"[green]Anthropic called tool:[/green] {tool_use_block.name} with {tool_use_block.input}")
        result = get_service_health(**tool_use_block.input)

        # In Anthropic, append assistant response, then append user message with type='tool_result'
        messages.append({"role": "assistant", "content": response.content})
        messages.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use_block.id,
                        "content": json.dumps(result),
                    }
                ],
            }
        )

        final_res = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=1024,
            messages=messages,
        )
        text_out = "".join(b.text for b in final_res.content if b.type == "text")
        console.print(f"[bold]Final Answer:[/bold] {text_out}")


def main():
    try:
        demo_openai_tool_call()
    except Exception as e:
        console.print(f"[red]OpenAI tool error: {e}[/red]")

    try:
        demo_anthropic_tool_call()
    except Exception as e:
        console.print(f"[red]Anthropic tool error: {e}[/red]")


if __name__ == "__main__":
    main()

