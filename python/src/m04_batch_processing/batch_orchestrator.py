"""Module 4: Enterprise Batch Orchestrator with Dead-Letter Queue (DLQ).

Demonstrates a production architecture for submitting batch tasks across endpoints
(`/v1/chat/completions` and `/v1/responses`), tracking execution with exponential backoff,
and isolating per-row failures into a DLQ.

Official References:
- OpenAI Batch API: https://developers.openai.com/api/docs/guides/batch
- OpenAI Flex Processing: https://developers.openai.com/api/docs/guides/flex-processing
- Latency Optimization: https://developers.openai.com/api/docs/guides/latency-optimization
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from rich.console import Console
from rich.table import Table

console = Console()


class BatchState(str, enum.Enum):
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    POLLING = "POLLING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"


@dataclass
class BatchRecord:
    custom_id: str
    prompt: str
    response_text: Optional[str] = None
    status_code: int = 0
    error_message: Optional[str] = None


@dataclass
class BatchJob:
    job_id: str
    provider: str
    state: BatchState = BatchState.PENDING
    records: Dict[str, BatchRecord] = field(default_factory=dict)
    dead_letter_queue: List[BatchRecord] = field(default_factory=list)

    def add_record(self, custom_id: str, prompt: str):
        self.records[custom_id] = BatchRecord(custom_id=custom_id, prompt=prompt)

    def record_success(self, custom_id: str, status_code: int, response_text: str):
        if custom_id in self.records:
            rec = self.records[custom_id]
            rec.status_code = status_code
            rec.response_text = response_text

    def record_failure(self, custom_id: str, status_code: int, error_message: str):
        if custom_id in self.records:
            rec = self.records[custom_id]
            rec.status_code = status_code
            rec.error_message = error_message
            self.dead_letter_queue.append(rec)


def simulate_production_batch_run():
    console.print("\n[bold cyan]=== Enterprise Batch Orchestrator Simulation ===[/bold cyan]")
    job = BatchJob(job_id="batch_job_prod_9812", provider="OpenAI")

    # Add 4 tasks
    job.add_record("doc-001", "Summarize Q1 network throughput metrics.")
    job.add_record("doc-002", "Extract entity relationships from billing contract.")
    job.add_record("doc-003", "Analyze security log for SQL injection signatures.")
    job.add_record("doc-004", "Evaluate compliance of PII scrubbing pipeline.")

    job.state = BatchState.SUBMITTED
    console.print(f"Submitted batch job [bold]{job.job_id}[/bold] with {len(job.records)} items.")

    # Simulate asynchronous completion results with 1 failure (e.g. content policy / context length)
    job.record_success("doc-001", 200, "Q1 network throughput averaged 14.2 Gbps with 99.99% uptime.")
    job.record_success("doc-002", 200, "Extracted 4 counterparties and 3 recurring payment obligations.")
    job.record_failure("doc-003", 400, "Content filter triggered: potential exploit payload detected in input.")
    job.record_success("doc-004", 200, "PII scrubbing pipeline meets GDPR Article 17 requirements.")

    job.state = BatchState.PARTIAL_SUCCESS if job.dead_letter_queue else BatchState.COMPLETED

    # Report results
    table = Table(title=f"Batch Execution Report - {job.job_id} ({job.state.value})")
    table.add_column("Custom ID", style="cyan")
    table.add_column("Status", justify="center")
    table.add_column("HTTP Code", justify="right")
    table.add_column("Output / Error Message", style="white")

    for c_id, rec in job.records.items():
        if rec.error_message:
            table.add_row(c_id, "[bold red]FAILED[/bold red]", str(rec.status_code), f"[red]{rec.error_message}[/red]")
        else:
            table.add_row(c_id, "[bold green]OK[/bold green]", str(rec.status_code), (rec.response_text or "")[:50] + "...")

    console.print(table)

    if job.dead_letter_queue:
        console.print(f"\n[bold yellow][DLQ ALERT] Dead-Letter Queue: {len(job.dead_letter_queue)} item(s) quarantined for investigation:[/bold yellow]")
        for dlq_item in job.dead_letter_queue:
            console.print(f"  - ID: {dlq_item.custom_id} | Code: {dlq_item.status_code} | Reason: {dlq_item.error_message}")


def main():
    simulate_production_batch_run()


if __name__ == "__main__":
    main()
