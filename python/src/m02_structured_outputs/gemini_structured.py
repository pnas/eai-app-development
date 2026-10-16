"""Module 2: Google Gemini Structured Outputs.

Demonstrates using Gemini's native response_schema and response_mime_type
with Pydantic models.
"""

from __future__ import annotations

import json
from rich.console import Console
from rich.panel import Panel
from google.genai import types as gemini_types
from src.m01_paradigms.client_factory import get_gemini_client
from src.m02_structured_outputs.models import SystemArchitectureSpec

console = Console()

ARCH_PROMPT = """
Perform an architectural assessment of our customer-facing payment gateway.
It currently consists of a monolithic Django app connected to a single un-replicated PostgreSQL
instance hosted in AWS us-east-1. We experience 250 requests/sec at peak, and daily downtime
during database backups. The team estimates running costs around $4,200/month.
"""


def get_gemini_clean_schema() -> dict:
    """Strip additionalProperties from Pydantic schema to comply with Google GenAI API."""
    import copy
    schema = copy.deepcopy(SystemArchitectureSpec.model_json_schema())

    def _strip_additional_properties(node):
        if isinstance(node, dict):
            node.pop("additionalProperties", None)
            for value in node.values():
                _strip_additional_properties(value)
        elif isinstance(node, list):
            for item in node:
                _strip_additional_properties(item)

    _strip_additional_properties(schema)
    return schema


def extract_with_gemini_schema() -> SystemArchitectureSpec:
    client = get_gemini_client()
    clean_schema = get_gemini_clean_schema()

    primary_model = "gemini-3.8-flash"
    fallback_model = "gemini-2.5-flash"

    console.print(f"[green]Calling Google Gemini ({primary_model}) with native response_schema...[/green]")
    try:
        response = client.models.generate_content(
            model=primary_model,
            contents=ARCH_PROMPT,
            config=gemini_types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=clean_schema,
                temperature=0.1,
            ),
        )
    except Exception as err:
        console.print(f"[yellow]Primary {primary_model} failed ({err}), falling back to {fallback_model}...[/yellow]")
        response = client.models.generate_content(
            model=fallback_model,
            contents=ARCH_PROMPT,
            config=gemini_types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=clean_schema,
                temperature=0.1,
            ),
        )

    if not response.text:
        raise ValueError("Empty response received from Gemini")

    # Validate output string into Pydantic model
    validated_spec : SystemArchitectureSpec = SystemArchitectureSpec.model_validate_json(response.text)
    return validated_spec


def main():
    try:
        spec : SystemArchitectureSpec = extract_with_gemini_schema()
        console.print(Panel(
            f"[bold green]System Name:[/bold green] {spec.system_name}\n"
            f"[bold]Scalability Rating:[/bold] {spec.scalability_rating_1_to_10}/10\n"
            f"[bold]Estimated Monthly Cost:[/bold] ${spec.estimated_monthly_tco_usd:,.2f}\n"
            f"[bold yellow]Identified Risks ({len(spec.risks)}):[/bold yellow]\n" +
            "\n".join([f"  - [{r.risk_level.value}] {r.component_name}: {r.description}" for r in spec.risks]) +
            f"\n\n[bold cyan]Recommended Patterns:[/bold cyan] {', '.join(spec.recommended_patterns)}",
            title="Google Gemini Response Schema Output",
            border_style="green"
        ))
    except Exception as e:
        console.print(f"[red]Gemini structured output error: {e}[/red]")


if __name__ == "__main__":
    main()

