"""Module 2: Self-Healing JSON & Output Repair Loop.

Demonstrates handling validation failures, truncated outputs due to max_tokens,
and automatically running a self-correction feedback loop.
"""

from __future__ import annotations

import json
from rich.console import Console
from pydantic import ValidationError
from src.m01_paradigms.client_factory import get_openai_client
from src.m02_structured_outputs.models import SystemArchitectureSpec

console = Console()


def repair_malformed_payload(
    corrupted_json_or_partial: str,
    error_message: str,
    max_repair_attempts: int = 2,
) -> SystemArchitectureSpec:
    """Take a broken or truncated JSON payload and prompt the model to repair it."""
    client = get_openai_client()

    current_payload = corrupted_json_or_partial
    current_error = error_message

    for attempt in range(1, max_repair_attempts + 1):
        console.print(f"[yellow]Attempt {attempt}: Running self-repair loop...[/yellow]")
        repair_prompt = f"""
The following JSON payload failed Pydantic validation:
---
{current_payload}
---
The validation / syntax error was:
{current_error}

Fix all syntax errors, close any unclosed brackets or strings, and return ONLY
a valid JSON object adhering strictly to the required schema.
"""
        response = client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an automated JSON schema repair engine."},
                {"role": "user", "content": repair_prompt},
            ],
            response_format=SystemArchitectureSpec,
        )

        try:
            parsed = response.choices[0].message.parsed
            if parsed:
                console.print("[bold green]Successfully repaired JSON schema![/bold green]")
                return parsed
        except Exception as e:
            current_error = str(e)
            current_payload = response.choices[0].message.content or ""

    raise RuntimeError(f"Failed to repair payload after {max_repair_attempts} attempts.")


def main():
    # Intentionally malformed & truncated payload (e.g. cut off by max_tokens)
    broken_truncated_json = """
    {
      "system_name": "Legacy Core Banking Gateway",
      "estimated_monthly_tco_usd": 12500.50,
      "scalability_rating_1_to_10": 3,
      "risks": [
        {
          "component_name": "Mainframe MQ Connector",
          "risk_level": "CRITICAL",
          "description": "Single point of failure with no failover cluster",
          "mitigation_strategy": "Migrate to Apache Kafka with multi-AZ replication"
        },
        {
          "component_name": "Session Store",
          "risk_level": "HIGH",
          "description": "In-memory state prevents horiz
    """
    console.print("[bold red]Simulating malformed/truncated LLM response:[/bold red]")
    console.print(broken_truncated_json)

    try:
        # Validate - will raise JSONDecodeError
        json.loads(broken_truncated_json)
    except Exception as err:
        console.print(f"[bold red]Detected Parsing Error:[/bold red] {err}")
        try:
            repaired_spec = repair_malformed_payload(broken_truncated_json, str(err))
            console.print(f"[green]Repaired System:[/green] {repaired_spec.system_name}")
            console.print(f"[green]Risks count:[/green] {len(repaired_spec.risks)}")
            for r in repaired_spec.risks:
                console.print(f"  - [{r.risk_level.value}] {r.component_name}: {r.description}")
        except Exception as repair_err:
            console.print(f"[red]Repair failed: {repair_err}[/red]")


if __name__ == "__main__":
    main()

