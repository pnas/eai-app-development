"""Module 2: Anthropic Constrained Structured Output Pattern.

Demonstrates using Anthropic's tool-choice mechanism to enforce 100% compliant
JSON schema extraction against Pydantic models.
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


def extract_with_anthropic_tool_choice() -> SystemArchitectureSpec:
    client = get_anthropic_client()

    schema = SystemArchitectureSpec.model_json_schema()
    tool_name = "emit_architecture_spec"

    tools = [
        {
            "name": tool_name,
            "description": "Emit formal architectural review specification.",
            "input_schema": schema,
        }
    ]

    console.print("[magenta]Calling Anthropic Claude with forced tool schema...[/magenta]")
    response = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=2048,
        tools=tools,
        tool_choice={"type": "tool", "name": tool_name},
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
        spec = extract_with_anthropic_tool_choice()
        console.print(Panel(
            f"[bold green]System Name:[/bold green] {spec.system_name}\n"
            f"[bold]Scalability Rating:[/bold] {spec.scalability_rating_1_to_10}/10\n"
            f"[bold]Estimated Monthly Cost:[/bold] ${spec.estimated_monthly_tco_usd:,.2f}\n"
            f"[bold yellow]Identified Risks ({len(spec.risks)}):[/bold yellow]\n" +
            "\n".join([f"  - [{r.risk_level.value}] {r.component_name}: {r.description}" for r in spec.risks]) +
            f"\n\n[bold cyan]Recommended Patterns:[/bold cyan] {', '.join(spec.recommended_patterns)}",
            title="Anthropic Constrained Tool-Use Output",
            border_style="magenta"
        ))
    except Exception as e:
        console.print(f"[red]Anthropic structured output error: {e}[/red]")


if __name__ == "__main__":
    main()

