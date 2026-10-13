"""Module 2: OpenAI Predicted Outputs & Speculative Decoding Demo.

Demonstrates using Predicted Outputs (`prediction={"type": "content", "content": ...}`)
to dramatically reduce latency (up to 2-4x speedup) for tasks with high token overlap,
such as code refactoring, document editing, and JSON regeneration.

Official References:
- Predicted Outputs: https://developers.openai.com/api/docs/guides/predicted-outputs
- Latency Optimization: https://developers.openai.com/api/docs/guides/latency-optimization
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict
from rich.console import Console
from rich.table import Table

from src.m01_paradigms.client_factory import get_openai_client

console = Console()

# Example code to refactor: adding type hints and docstrings
SAMPLE_ORIGINAL_CODE = '''def calculate_sla_uptime(downtime_minutes, total_minutes=43200):
    if total_minutes <= 0:
        return 0.0
    uptime_minutes = total_minutes - downtime_minutes
    return (uptime_minutes / total_minutes) * 100.0
'''

SAMPLE_PROMPT = """Refactor this Python function to include PEP 484 type hints and a Google-style docstring:

```python
def calculate_sla_uptime(downtime_minutes, total_minutes=43200):
    if total_minutes <= 0:
        return 0.0
    uptime_minutes = total_minutes - downtime_minutes
    return (uptime_minutes / total_minutes) * 100.0
```
"""


def benchmark_predicted_outputs(
    original_code: str = SAMPLE_ORIGINAL_CODE,
    prompt: str = SAMPLE_PROMPT,
    model: str = "gpt-4.1-mini",
    use_mock_fallback: bool = True,
) -> Dict[str, Any]:
    """Execute refactor with and without Predicted Outputs, comparing latency and tokens."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key.startswith("mock") or api_key.startswith("sk-placeholder"):
        if use_mock_fallback:
            console.print("[yellow][Simulated Offline Benchmark] Measuring speculative decoding savings...[/yellow]")
            return {
                "standard": {
                    "latency_sec": 1.48,
                    "completion_tokens": 120,
                    "accepted_prediction_tokens": 0,
                    "rejected_prediction_tokens": 0,
                    "result": "def calculate_sla_uptime(downtime_minutes: int, total_minutes: int = 43200) -> float:\n    \"\"\"Calculate telecom SLA uptime percentage.\"\"\"\n    ...",
                },
                "speculative": {
                    "latency_sec": 0.42,
                    "completion_tokens": 120,
                    "accepted_prediction_tokens": 92,
                    "rejected_prediction_tokens": 8,
                    "result": "def calculate_sla_uptime(downtime_minutes: int, total_minutes: int = 43200) -> float:\n    \"\"\"Calculate telecom SLA uptime percentage.\"\"\"\n    ...",
                },
                "speedup_factor": 3.52,
                "token_acceptance_rate": 92.0,
            }
        raise ValueError("Missing or mock OPENAI_API_KEY environment variable.")

    client = get_openai_client()

    # 1. Standard Generation (Baseline)
    t0 = time.perf_counter()
    res_standard = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are an expert Python engineer. Return only updated code."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.0,
    )
    t_standard = time.perf_counter() - t0

    # 2. Speculative Generation with Predicted Outputs
    t0 = time.perf_counter()
    res_predicted = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are an expert Python engineer. Return only updated code."},
            {"role": "user", "content": prompt},
        ],
        prediction={"type": "content", "content": original_code},
        temperature=0.0,
    )
    t_predicted = time.perf_counter() - t0

    usage_std = res_standard.usage
    usage_pred = res_predicted.usage
    pred_details = getattr(usage_pred, "completion_tokens_details", None)
    accepted = getattr(pred_details, "accepted_prediction_tokens", 0) or 0
    rejected = getattr(pred_details, "rejected_prediction_tokens", 0) or 0

    total_predicted = accepted + rejected
    acceptance_rate = (accepted / total_predicted * 100.0) if total_predicted > 0 else 0.0
    speedup = t_standard / t_predicted if t_predicted > 0 else 1.0

    return {
        "standard": {
            "latency_sec": round(t_standard, 3),
            "completion_tokens": usage_std.completion_tokens if usage_std else 0,
            "accepted_prediction_tokens": 0,
            "rejected_prediction_tokens": 0,
            "result": res_standard.choices[0].message.content,
        },
        "speculative": {
            "latency_sec": round(t_predicted, 3),
            "completion_tokens": usage_pred.completion_tokens if usage_pred else 0,
            "accepted_prediction_tokens": accepted,
            "rejected_prediction_tokens": rejected,
            "result": res_predicted.choices[0].message.content,
        },
        "speedup_factor": round(speedup, 2),
        "token_acceptance_rate": round(acceptance_rate, 1),
    }


def main():
    console.print("\n[bold cyan]=== OpenAI Predicted Outputs & Speculative Decoding Benchmark ===[/bold cyan]")
    data = benchmark_predicted_outputs(use_mock_fallback=True)

    table = Table(title="Speculative Decoding vs. Standard Generation")
    table.add_column("Metric", style="bold")
    table.add_column("Standard Generation", style="yellow")
    table.add_column("Predicted Outputs (Speculative)", style="green")

    std = data["standard"]
    spec = data["speculative"]

    table.add_row("Latency (seconds)", f"{std['latency_sec']}s", f"{spec['latency_sec']}s")
    table.add_row("Speedup", "1.0x (Baseline)", f"[bold]{data['speedup_factor']}x Faster[/bold]")
    table.add_row("Completion Tokens", str(std["completion_tokens"]), str(spec["completion_tokens"]))
    table.add_row("Accepted Prediction Tokens", str(std["accepted_prediction_tokens"]), f"[bold]{spec['accepted_prediction_tokens']}[/bold]")
    table.add_row("Rejected Prediction Tokens", str(std["rejected_prediction_tokens"]), str(spec["rejected_prediction_tokens"]))
    table.add_row("Acceptance Ratio", "N/A", f"{data['token_acceptance_rate']}%")

    console.print(table)
    console.print("\n[dim]Key Insight: Predicted outputs use speculative decoding to verify predicted token chunks in parallel, matching the exact KV stream while cutting latency by up to 75%.[/dim]")


if __name__ == "__main__":
    main()
