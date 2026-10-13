"""Module 2 (LangChain): Grammar-Constrained Structured Outputs with Pydantic v2.

Contrasts manual JSON mode parsing with LangChain's .with_structured_output():
1. Pydantic v2 schema extraction with strict validation.
2. Cross-provider consistency (OpenAI strict JSON schema vs Anthropic tool-calling vs Gemini schema).
3. Schema self-repair and error handling on malformed extraction.
"""

from __future__ import annotations

import os
from typing import Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field
from rich.console import Console
from rich.panel import Panel

from src.langchain_suite.core.models import get_chat_model

console = Console()


class TelecomIncidentTriage(BaseModel):
    """Schema for automated network incident classification and routing."""

    incident_id: str = Field(description="Unique ticket identifier formatted as TICKET-XXXX")
    severity: Literal["P1-CRITICAL", "P2-HIGH", "P3-MEDIUM", "P4-LOW"] = Field(
        description="Assigned outage severity SLA priority"
    )
    affected_subsystems: List[Literal["5G-RAN", "CORE-EPC", "IMS-VOICE", "FIBER-BACKHAUL", "BSS-BILLING"]] = (
        Field(description="Subsystems affected by this anomaly")
    )
    root_cause_hypothesis: str = Field(description="Probable root cause summary")
    recommended_action: str = Field(description="Immediate mitigation playbook step")
    estimated_impact_subscribers: int = Field(ge=0, description="Estimated affected customer count")


def _has_key_for_provider(provider: str) -> bool:
    if provider == "openai":
        return bool(os.getenv("OPENAI_API_KEY"))
    if provider == "anthropic":
        return bool(os.getenv("ANTHROPIC_API_KEY"))
    if provider == "gemini":
        return bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
    return False


def run_structured_extraction(
    incident_report: str,
    provider: str = "openai",
) -> TelecomIncidentTriage:
    """Extracts typed Pydantic v2 object using grammar-constrained output across providers."""
    if not _has_key_for_provider(provider):
        console.print(f"[yellow][Notice] Missing key for {provider}. Returning mock triage.[/yellow]")
        return TelecomIncidentTriage(
            incident_id="TICKET-9942",
            severity="P1-CRITICAL",
            affected_subsystems=["5G-RAN", "FIBER-BACKHAUL", "IMS-VOICE"],
            root_cause_hypothesis="Third-party roadwork severed secondary dark fiber conduit",
            recommended_action="Reroute control plane and deploy fiber repair team",
            estimated_impact_subscribers=18500,
        )

    model = get_chat_model(provider, temperature=0.0)

    # LangChain automatically configures provider-specific constrained decoding
    # (e.g. OpenAI json_schema with strict: true, Anthropic tool use, Gemini structured output)
    structured_llm = model.with_structured_output(TelecomIncidentTriage)

    console.print(f"[bold cyan]Extracting structured triage with Pydantic v2 via {provider.upper()}...[/bold cyan]")
    triage: TelecomIncidentTriage = structured_llm.invoke(incident_report)
    return triage


def compare_structured_extraction(
    incident_report: str,
    providers: Optional[List[str]] = None,
) -> Dict[str, Union[TelecomIncidentTriage, str]]:
    """Compares structured extraction across OpenAI, Anthropic, and Gemini."""
    if providers is None:
        providers = ["openai", "anthropic", "gemini"]

    console.print("\n[bold yellow]=== Cross-Provider Structured Extraction Comparison ===[/bold yellow]\n")
    results: Dict[str, Union[TelecomIncidentTriage, str]] = {}

    for provider in providers:
        try:
            res = run_structured_extraction(incident_report, provider=provider)
            results[provider] = res
            console.print(f"[green]✔ {provider.upper()} extracted:[/green] {res.incident_id} ({res.severity})")
        except Exception as e:
            console.print(f"[red]✘ {provider.upper()} failed: {e}[/red]")
            results[provider] = f"ERROR: {e}"

    return results


if __name__ == "__main__":
    sample_report = """
    URGENT OUTAGE REPORT: Incident TICKET-9942 reported at 14:22 UTC.
    Multiple eNodeB base stations in Frankfurt South cluster lost synchronization.
    Fiber backhaul rings experiencing 45% packet drop after third-party roadwork severed secondary dark fiber conduit.
    Voice IMS calls dropping; estimated 18,500 active mobile subscribers experiencing service degradation.
    """

    compare_structured_extraction(sample_report)
