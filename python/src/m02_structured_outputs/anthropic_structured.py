"""Module 2: Anthropic Structured Output Paradigms.

Demonstrates modern Claude structured output extraction:
1. Native Structured Outputs via `client.messages.parse(output_format=...)` with grammar compilation.
2. Strict Tool Calling via `strict: True` and JSON Schema validation.

Reference:
- https://platform.claude.com/docs/en/build-with-claude/structured-outputs
- https://platform.claude.com/docs/en/build-with-claude/working-with-messages
"""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from src.m01_paradigms.client_factory import get_anthropic_client
from src.m02_structured_outputs.models import SystemArchitectureSpec

console = Console()

ARCH_PROMPT = """
Perform an architectural assessment of our customer-facing payment gateway.
It currently consists of a monolithic Django app connected to a single un-replicated PostgreSQL
instance hosted in AWS us-east-1. We experience 250 requests/sec at peak, and daily downtime
during database backups. The team estimates running costs around $4,200/month.
"""


def extract_with_native_parse() -> SystemArchitectureSpec:
    """Extract structured data natively using Claude 5.5 SDK parser.
    
    Uses `client.messages.parse()` with Pydantic model specification.
    Note: Structured Outputs does NOT support prefilled assistant responses or Citations.
    Do not pass temperature or top_p to Claude 4.7+/5.x models.
    """
    client = get_anthropic_client()
    console.print("[magenta]Calling Anthropic Claude (claude-sonnet-5-5) with native client.messages.parse()...[/magenta]")

    # SDK parses response directly into the specified Pydantic model
    response = client.messages.parse(
        model="claude-sonnet-5-5",
        max_tokens=2048,
        output_format=SystemArchitectureSpec,
        output_config={"effort": "medium"},
        messages=[
            {
                "role": "user",
                "content": f"Analyze the following architecture and emit the formal spec:\n{ARCH_PROMPT}",
            }
        ],
    )
    return response.parsed_output


def extract_with_anthropic_strict_tool() -> SystemArchitectureSpec:
    """Extract structured data using strict tool calling (alternative schema enforcement).
    
    Requires:
    - strict: True
    - additionalProperties: False
    - tool_choice: {"type": "tool", "name": tool_name}
    """
    client = get_anthropic_client()

    schema = SystemArchitectureSpec.model_json_schema()
    schema["additionalProperties"] = False
    tool_name = "emit_architecture_spec"

    tools = [
        {
            "name": tool_name,
            "description": "Emit formal architectural review specification.",
            "input_schema": schema,
            "strict": True,
        }
    ]

    console.print("[magenta]Calling Anthropic Claude (claude-sonnet-5-5) with strict tool calling...[/magenta]")
    response = client.messages.create(
        model="claude-sonnet-5-5",
        max_tokens=2048,
        tools=tools,
        tool_choice={"type": "tool", "name": tool_name},
        output_config={"effort": "medium"},
        messages=[
            {
                "role": "user",
                "content": f"Analyze the following architecture and emit the formal spec:\n{ARCH_PROMPT}",
            }
        ],
    )

    # Find the tool use block
    tool_use = next((b for b in response.content if b.type == "tool_use"), None)
    if not tool_use:
        raise ValueError("Model failed to invoke forced tool")

    # Validate tool inputs directly back into Pydantic model
    validated_spec = SystemArchitectureSpec.model_validate(tool_use.input)
    return validated_spec


def main():
    try:
        spec = extract_with_native_parse()
        console.print(Panel(
            f"[bold green]System Name:[/bold green] {spec.system_name}\n"
            f"[bold]Scalability Rating:[/bold] {spec.scalability_rating_1_to_10}/10\n"
            f"[bold]Estimated Monthly Cost:[/bold] ${spec.estimated_monthly_tco_usd:,.2f}\n"
            f"[bold yellow]Identified Risks ({len(spec.risks)}):[/bold yellow]\n" +
            "\n".join([f"  - [{r.risk_level.value}] {r.component_name}: {r.description}" for r in spec.risks]) +
            f"\n\n[bold cyan]Recommended Patterns:[/bold cyan] {', '.join(spec.recommended_patterns)}",
            title="Anthropic Native Structured Output (claude-sonnet-5-5)",
            border_style="magenta"
        ))
    except Exception as e:
        console.print(f"[yellow]Falling back to strict tool calling due to mock/network: {e}[/yellow]")
        try:
            spec = extract_with_anthropic_strict_tool()
            console.print(Panel(
                f"[bold green]System Name:[/bold green] {spec.system_name}\n"
                f"[bold]Scalability Rating:[/bold] {spec.scalability_rating_1_to_10}/10\n"
                f"[bold]Estimated Monthly Cost:[/bold] ${spec.estimated_monthly_tco_usd:,.2f}\n"
                f"[bold yellow]Identified Risks ({len(spec.risks)}):[/bold yellow]\n" +
                "\n".join([f"  - [{r.risk_level.value}] {r.component_name}: {r.description}" for r in spec.risks]) +
                f"\n\n[bold cyan]Recommended Patterns:[/bold cyan] {', '.join(spec.recommended_patterns)}",
                title="Anthropic Strict Tool-Choice Output (claude-sonnet-5-5)",
                border_style="magenta"
            ))
        except Exception as inner_e:
            console.print(f"[red]Anthropic structured output error: {inner_e}[/red]")


if __name__ == "__main__":
    main()
