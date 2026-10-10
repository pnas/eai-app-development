"""Module 2 (LangChain): Grammar-Constrained Structured Outputs with Pydantic v2.

Contrasts manual JSON mode parsing with LangChain's .with_structured_output():
1. Pydantic v2 schema extraction with strict validation.
2. Cross-provider consistency (OpenAI strict JSON schema vs Anthropic tool-calling vs Gemini schema).
3. Schema self-repair and error handling on malformed extraction.
"""

from __future__ import annotations

from typing import List, Literal, Optional
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


def run_structured_extraction(incident_report: str) -> TelecomIncidentTriage:
    """Extracts typed Pydantic v2 object using grammar-constrained output."""
    model = get_chat_model("openai", temperature=0.0)

    # LangChain automatically configures provider-specific constrained decoding
    # (e.g. OpenAI json_schema with strict: true)
    structured_llm = model.with_structured_output(TelecomIncidentTriage)

    console.print("[bold cyan]Extracting structured triage with Pydantic v2...[/bold cyan]")
    triage: TelecomIncidentTriage = structured_llm.invoke(incident_report)
    return triage


if __name__ == "__main__":
    sample_report = """
    URGENT OUTAGE REPORT: Incident TICKET-9942 reported at 14:22 UTC.
    Multiple eNodeB base stations in Frankfurt South cluster lost synchronization.
    Fiber backhaul rings experiencing 45% packet drop after third-party roadwork severed secondary dark fiber conduit.
    Voice IMS calls dropping; estimated 18,500 active mobile subscribers experiencing service degradation.
    """

    console.print("\n[bold yellow]=== Module 2: Structured Outputs with LangChain ===[/bold yellow]\n")
    result = run_structured_extraction(sample_report)

    console.print(Panel.fit(
        f"[bold green]Ticket:[/bold green] {result.incident_id}\n"
        f"[bold red]Severity:[/bold red] {result.severity}\n"
        f"[bold yellow]Subsystems:[/bold yellow] {', '.join(result.affected_subsystems)}\n"
        f"[bold cyan]Subscribers Affected:[/bold cyan] {result.estimated_impact_subscribers:,}\n"
        f"[bold white]Hypothesis:[/bold white] {result.root_cause_hypothesis}\n"
        f"[bold magenta]Playbook Action:[/bold magenta] {result.recommended_action}",
        title="Parsed Telecom Incident",
    ))

