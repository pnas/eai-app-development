"""Module 2: OpenAI Strict Structured Outputs.

Demonstrates using client.beta.chat.completions.parse with Pydantic models,
leveraging Context-Free Grammar (CFG) constrained decoding.
"""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from src.m01_paradigms.client_factory import get_openai_client
from src.m02_structured_outputs.models import SystemArchitectureSpec

console = Console()

ARCH_PROMPT = """
Perform an architectural assessment of our customer-facing payment gateway.
It currently consists of a monolithic Django app connected to a single un-replicated PostgreSQL
instance hosted in AWS us-east-1. We experience 250 requests/sec at peak, and daily downtime
during database backups. The team estimates running costs around $4,200/month.
"""


def extract_with_openai_strict() -> SystemArchitectureSpec:
    client = get_openai_client()

    console.print("[cyan]Sending request to OpenAI with strict Pydantic grammar...[/cyan]")
    # Using the beta parse method automatically injects json_schema with strict: True
    completion = client.beta.chat.completions.parse(
        model="gpt-4o-2024-08-06",
        messages=[
            {"role": "system", "content": "You are a Principal Cloud Systems Architect."},
            {"role": "user", "content": ARCH_PROMPT},
        ],
        response_format=SystemArchitectureSpec,
    )

    message = completion.choices[0].message
    # If the response was refused due to safety policy, refusal is populated
    if message.refusal:
        raise RuntimeError(f"Model refused output: {message.refusal}")

    parsed_spec: SystemArchitectureSpec = message.parsed
    return parsed_spec


def main():
    try:
        spec = extract_with_openai_strict()
        console.print(Panel(
            f"[bold green]System Name:[/bold green] {spec.system_name}\n"
            f"[bold]Scalability Rating:[/bold] {spec.scalability_rating_1_to_10}/10\n"
            f"[bold]Estimated Monthly Cost:[/bold] ${spec.estimated_monthly_tco_usd:,.2f}\n"
            f"[bold yellow]Identified Risks ({len(spec.risks)}):[/bold yellow]\n" +
            "\n".join([f"  - [{r.risk_level.value}] {r.component_name}: {r.description}" for r in spec.risks]) +
            f"\n\n[bold cyan]Recommended Patterns:[/bold cyan] {', '.join(spec.recommended_patterns)}",
            title="OpenAI Strict Response API Output",
            border_style="green"
        ))
    except Exception as e:
        console.print(f"[red]Execution failed: {e}[/red]")


if __name__ == "__main__":
    main()

