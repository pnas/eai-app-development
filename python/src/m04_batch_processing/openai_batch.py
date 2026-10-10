"""Module 4: OpenAI Batch API Pipeline.

Demonstrates:
1. Formatting requests into .jsonl with custom_ids.
2. Uploading the batch file via client.files.create(purpose="batch").
3. Submitting the batch job with 24h completion window (50% discount).
4. Polling with exponential backoff until completion.
5. Downloading and correlating line-by-line responses.
"""

from __future__ import annotations

import io
import json
import time
from typing import Dict, Any, List
from rich.console import Console
from rich.table import Table
from src.m01_paradigms.client_factory import get_openai_client

console = Console()


def create_sample_batch_payload() -> str:
    """Create in-memory JSONL string of requests with custom correlation IDs."""
    prompts = [
        ("task-001", "Classify sentiment: 'The migration was flawless and latency dropped 40%'"),
        ("task-002", "Classify sentiment: 'Database connection timeouts caused an outage on Friday'"),
        ("task-003", "Classify sentiment: 'The new pricing model is acceptable but documentation is sparse'"),
    ]

    buffer = io.StringIO()
    for custom_id, user_text in prompts:
        row = {
            "custom_id": custom_id,
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": {
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": "Respond with one word: POSITIVE, NEGATIVE, or NEUTRAL."},
                    {"role": "user", "content": user_text},
                ],
                "max_tokens": 10,
            },
        }
        buffer.write(json.dumps(row) + "\n")

    return buffer.getvalue()


def run_openai_batch_workflow():
    client = get_openai_client()

    console.print("\n[bold cyan]1. Generating JSONL batch payload...[/bold cyan]")
    jsonl_content = create_sample_batch_payload()
    console.print(f"Generated {len(jsonl_content.splitlines())} batch tasks.")

    console.print("[bold cyan]2. Uploading batch file to OpenAI Files API...[/bold cyan]")
    file_bytes = io.BytesIO(jsonl_content.encode("utf-8"))
    uploaded_file = client.files.create(
        file=("batch_requests.jsonl", file_bytes, "application/jsonl"),
        purpose="batch",
    )
    console.print(f"[green]File uploaded successfully![/green] File ID: {uploaded_file.id}")

    console.print("[bold cyan]3. Creating batch job (50% cost discount)...[/bold cyan]")
    batch_job = client.batches.create(
        input_file_id=uploaded_file.id,
        endpoint="/v1/chat/completions",
        completion_window="24h",
        metadata={"course": "advanced-ai-integration", "environment": "training"},
    )
    console.print(f"[green]Batch job submitted![/green] Batch ID: {batch_job.id}, Status: {batch_job.status}")

    console.print("[bold cyan]4. Polling batch status (with backoff)...[/bold cyan]")
    poll_interval = 5
    max_wait_seconds = 180  # Limit wait time for demonstration
    start_time = time.time()

    completed_job = None
    while (time.time() - start_time) < max_wait_seconds:
        status = client.batches.retrieve(batch_job.id)
        counts = status.request_counts
        completed = counts.completed if counts else 0
        total = counts.total if counts else 0
        console.print(f"  Status: [yellow]{status.status}[/yellow] (Completed: {completed}/{total})")

        if status.status in ("completed", "failed", "expired", "cancelled"):
            completed_job = status
            break

        time.sleep(poll_interval)
        poll_interval = min(poll_interval * 1.5, 30)

    if not completed_job or completed_job.status != "completed":
        console.print(f"[yellow]Batch is still in progress (ID: {batch_job.id}). In production, batch runs asynchronously up to 24h.[/yellow]")
        return

    console.print("[bold cyan]5. Downloading batch results...[/bold cyan]")
    if completed_job.output_file_id:
        output_content = client.files.content(completed_job.output_file_id).text
        table = Table(title="Batch Output Results")
        table.add_column("Custom ID", style="cyan")
        table.add_column("HTTP Status", style="green")
        table.add_column("Model Response", style="white")

        for line in output_content.strip().split("\n"):
            result_row = json.loads(line)
            c_id = result_row["custom_id"]
            http_code = result_row["response"]["status_code"]
            choice = result_row["response"]["body"]["choices"][0]["message"]["content"]
            table.add_row(c_id, str(http_code), choice.strip())

        console.print(table)


def main():
    try:
        run_openai_batch_workflow()
    except Exception as e:
        console.print(f"[red]OpenAI batch error: {e}[/red]")


if __name__ == "__main__":
    main()

