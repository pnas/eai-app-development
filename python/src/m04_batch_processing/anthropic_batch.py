"""Module 4: Anthropic Message Batches API.

Demonstrates submitting asynchronous batch requests to Anthropic Claude
with custom IDs and inspecting batch processing state.
Batches receive 50% pricing discount on modern Claude models (e.g. claude-haiku-5-5).

Reference:
- https://platform.claude.com/docs/en/build-with-claude/working-with-messages
"""

from __future__ import annotations

import time
from rich.console import Console
from rich.table import Table
from src.m01_paradigms.client_factory import get_anthropic_client

console = Console()


def run_anthropic_batch_demo():
    client = get_anthropic_client()
    # Claude Haiku 5.5 is modern high-throughput batch model
    model = "claude-haiku-5-5"

    console.print("\n[bold magenta]1. Preparing Anthropic Message Batch requests...[/bold magenta]")
    requests = [
        {
            "custom_id": "review-101",
            "params": {
                "model": model,
                "max_tokens": 100,
                "messages": [
                    {"role": "user", "content": "Generate a 1-sentence code review tip for Python decorators."}
                ],
            },
        },
        {
            "custom_id": "review-102",
            "params": {
                "model": model,
                "max_tokens": 100,
                "messages": [
                    {"role": "user", "content": "Generate a 1-sentence code review tip for database transactions."}
                ],
            },
        },
    ]

    console.print("[bold magenta]2. Creating Message Batch (50% Cost Discount)...[/bold magenta]")
    try:
        message_batch = client.messages.batches.create(requests=requests)
    except Exception:
        # Fallback to claude-3-5-haiku-20241022 if key doesn't have 5.5 batch enabled yet
        for r in requests:
            r["params"]["model"] = "claude-3-5-haiku-20241022"
        message_batch = client.messages.batches.create(requests=requests)

    console.print(f"[green]Batch submitted![/green] Batch ID: {message_batch.id}, Status: {message_batch.processing_status}")

    console.print("[bold magenta]3. Inspecting batch status...[/bold magenta]")
    batch_status = client.messages.batches.retrieve(message_batch.id)
    counts = batch_status.request_counts

    table = Table(title="Anthropic Batch Status")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Batch ID", batch_status.id)
    table.add_row("Status", batch_status.processing_status)
    table.add_row("Processing Counts", f"Processing: {counts.processing}, Succeeded: {counts.succeeded}, Errored: {counts.errored}")
    table.add_row("Created At", str(batch_status.created_at))
    table.add_row("Expires At", str(batch_status.expires_at))

    console.print(table)
    console.print("\n[dim]In production, poll until processing_status == 'ended', then iterate through client.messages.batches.results(batch_id).[/dim]")


def main():
    try:
        run_anthropic_batch_demo()
    except Exception as e:
        console.print(f"[red]Anthropic batch error: {e}[/red]")


if __name__ == "__main__":
    main()
