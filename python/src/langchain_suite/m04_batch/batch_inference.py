"""Module 4 (LangChain): Concurrent Batch Inference & Throttling.

Contrasts provider-side 24-hour asynchronous Batch APIs with LangChain's
client-side concurrent batch execution:
1. Using model.abatch() / model.batch() with RunnableConfig(max_concurrency=N).
2. Avoiding rate-limit stampedes via client-side concurrency windows.
3. Gathering structured outputs in bulk.
"""

from __future__ import annotations

import asyncio
import time
from typing import List
from rich.console import Console
from rich.table import Table

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from src.langchain_suite.core.models import get_chat_model

console = Console()

TELECOM_QUERIES = [
    "Customer reports 4G fallback in central Berlin despite 5G SA subscription.",
    "BSS billing cycle failed for subscriber ID SUB-4401 due to currency mismatch.",
    "eNodeB antenna tilt misconfiguration suspected on sector 3, tower DE-BER-102.",
    "Optical line terminal (OLT) reports loss of signal (LOS) on PON port 4.",
    "Roaming handshake timeout with partner network in Switzerland.",
    "VoLTE SIP 408 Request Timeout during peak hour traffic.",
]


async def run_batch_pipeline(max_concurrency: int = 3) -> None:
    """Executes queries concurrently using LangChain's abatch with concurrency throttling."""
    model = get_chat_model("openai", temperature=0.0)

    system_prompt = "You are a network operations assistant. Provide a 1-sentence recommended action."
    prompts = [
        [SystemMessage(content=system_prompt), HumanMessage(content=q)]
        for q in TELECOM_QUERIES
    ]

    console.print(f"\n[bold yellow]=== Module 4: Concurrent Batching (Concurrency={max_concurrency}) ===[/bold yellow]\n")
    start = time.perf_counter()

    # Configure maximum concurrency to protect upstream rate limits
    config = RunnableConfig(max_concurrency=max_concurrency)
    results = await model.abatch(prompts, config=config)

    total_time = time.perf_counter() - start

    table = Table(title=f"Batch Results ({len(prompts)} queries completed in {total_time:.2f}s)")
    table.add_column("Query", style="cyan", max_width=45)
    table.add_column("Response", style="green", max_width=60)

    for query, response in zip(TELECOM_QUERIES, results):
        content = response.content if isinstance(response.content, str) else str(response.content)
        table.add_row(query, content.strip())

    console.print(table)


if __name__ == "__main__":
    asyncio.run(run_batch_pipeline(max_concurrency=3))

