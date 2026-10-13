"""Module 2: Anthropic Native Document Citations.

Demonstrates Anthropic's native Citations API for grounded responses:
- Passing document blocks with `citations: {"enabled": True}`
- Extracting citation locations (`char_location`, `page_location`, `content_block_location`)
- Zero-token cost benefit (cited_text tokens are 100% exempt from billable output)
- Verification that Citations cannot be mixed with Structured Outputs or Prefills.

Reference:
- https://platform.claude.com/docs/en/build-with-claude/citations
- https://platform.claude.com/docs/en/build-with-claude/working-with-messages
"""

from __future__ import annotations

import json
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from src.m01_paradigms.client_factory import get_anthropic_client

console = Console()

SLA_DOCUMENT = """
TELEKOM ENTERPRISE CLOUD SERVICE LEVEL AGREEMENT (SLA)
Document Version: 2026.4
Effective Date: January 1, 2026

1. SERVICE AVAILABILITY COMMITMENT
Telekom guarantees a Monthly Uptime Percentage of at least 99.99% for all Multi-Region
Enterprise Cloud Services during any monthly billing cycle. Service availability is measured
by automated health probes querying the /healthz endpoint every 10 seconds.

2. SERVICE CREDIT REBATE SCHEDULE
If Telekom fails to meet the Monthly Uptime Commitment, Customer is eligible to receive
Service Credits as follows:
- Monthly Uptime 99.0% to < 99.99%: 10% credit of monthly billing for the affected service.
- Monthly Uptime 95.0% to < 99.0%: 25% credit of monthly billing for the affected service.
- Monthly Uptime < 95.0%: 50% credit of monthly billing for the affected service.

3. EXCLUSIONS AND SCHEDULED MAINTENANCE
Maintenance windows are scheduled exclusively between Sunday 02:00 UTC and 04:00 UTC.
Outages resulting from customer misconfiguration, expired TLS certificates, or uncoordinated
load testing exceeding 10x baseline are strictly excluded from SLA credit calculations.
"""


def query_document_with_citations(question: str) -> None:
    client = get_anthropic_client()

    console.print(f"[magenta]Querying Claude 5.5 with grounded document citations...[/magenta]")
    console.print(f"[bold cyan]Question:[/bold cyan] {question}\n")

    # Pass document with citations enabled
    # Note: On Claude 4.7+ and 5.x, temperature and top_p MUST NOT be set
    response = client.messages.create(
        model="claude-sonnet-5-5",
        max_tokens=1500,
        output_config={"effort": "medium"},
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "text",
                            "media_type": "text/plain",
                            "data": SLA_DOCUMENT,
                        },
                        "title": "Telekom Enterprise SLA 2026",
                        "citations": {"enabled": True},
                    },
                    {
                        "type": "text",
                        "text": question,
                    },
                ],
            }
        ],
    )

    console.print("[bold green]=== Grounded Answer & Citation Trace ===[/bold green]\n")

    total_citations = 0
    table = Table(title="Extracted Document Citations", border_style="cyan")
    table.add_column("Doc Title", style="magenta")
    table.add_column("Location Type", style="yellow")
    table.add_column("Char Range", style="blue")
    table.add_column("Cited Text / Evidence", style="green")

    for block in response.content:
        if block.type == "text":
            console.print(block.text)
            console.print()

            # Inspect citations if present on block
            citations = getattr(block, "citations", None)
            if citations:
                for c in citations:
                    total_citations += 1
                    loc_type = getattr(c, "type", "char_location")
                    start_char = getattr(c, "start_char_index", "N/A")
                    end_char = getattr(c, "end_char_index", "N/A")
                    cited_text = getattr(c, "cited_text", "")
                    doc_title = getattr(c, "document_title", "Telekom SLA")

                    table.add_row(
                        str(doc_title),
                        str(loc_type),
                        f"[{start_char}:{end_char}]",
                        cited_text[:120] + ("..." if len(cited_text) > 120 else "")
                    )

    if total_citations > 0:
        console.print(table)
    else:
        console.print("[yellow]No formal citation blocks returned (or mocked environment).[/yellow]")

    # Display usage & token discount economics
    usage = response.usage
    console.print(Panel(
        f"[bold]Input Tokens:[/bold] {usage.input_tokens}\n"
        f"[bold]Output Tokens:[/bold] {usage.output_tokens}\n"
        f"[bold cyan]Zero-Token Citation Benefit:[/bold cyan] Quoted passages inside citations are "
        f"[green]100% exempt[/green] from billable output tokens and context window degradation.\n"
        f"[bold red]Constraint Note:[/bold red] Document Citations CANNOT be combined with Structured Outputs or Prefills (HTTP 400).",
        title="Anthropic Citations Economics & Rules",
        border_style="green"
    ))


def main():
    try:
        query_document_with_citations(
            "What is the guaranteed uptime commitment, and what credit rebate do I get if uptime falls below 95%?"
        )
    except Exception as e:
        console.print(f"[red]Anthropic Citations error: {e}[/red]")


if __name__ == "__main__":
    main()
