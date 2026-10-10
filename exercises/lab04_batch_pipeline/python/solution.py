"""Lab 04 Reference Solution: Batch API Cost Arbitrage Pipeline."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple


@dataclass
class CostSummary:
    total_prompt_tokens: int
    total_completion_tokens: int
    standard_cost_usd: float
    batch_discounted_cost_usd: float
    net_savings_usd: float
    successful_items: int
    failed_items: int


class BatchPipeline:
    """Orchestrator for Asynchronous Batch API jobs."""

    STANDARD_RATES = {
        "gpt-4o-mini": {"prompt": 0.15 / 1_000_000, "completion": 0.60 / 1_000_000},
        "gpt-4o": {"prompt": 2.50 / 1_000_000, "completion": 10.00 / 1_000_000},
    }

    @classmethod
    def generate_batch_jsonl(
        cls,
        items: List[Dict[str, str]],
        model: str = "gpt-4o-mini",
    ) -> str:
        """Serialize a list of items into an OpenAI-compliant Batch API JSONL string."""
        lines: List[str] = []
        for item in items:
            entry = {
                "custom_id": item["id"],
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": {
                    "model": model,
                    "messages": [{"role": "user", "content": item["prompt"]}],
                },
            }
            lines.append(json.dumps(entry))
        return "\n".join(lines)

    @classmethod
    def process_batch_results(
        cls,
        results_jsonl: str,
        model: str = "gpt-4o-mini",
    ) -> Tuple[Dict[str, Any], CostSummary]:
        """Parse raw batch results JSONL, isolating errors and calculating savings."""
        results: Dict[str, Any] = {}
        prompt_tokens = 0
        completion_tokens = 0
        successful_items = 0
        failed_items = 0

        for line in results_jsonl.strip().splitlines():
            if not line.strip():
                continue

            record = json.loads(line)
            cid = record.get("custom_id", "unknown")

            # Check if line had an error
            if "error" in record and record["error"] is not None:
                failed_items += 1
                results[cid] = {"status": "error", "error": record["error"]}
                continue

            response = record.get("response", {})
            status_code = response.get("status_code", 500)

            if status_code != 200:
                failed_items += 1
                results[cid] = {"status": "error", "status_code": status_code, "body": response.get("body")}
                continue

            body = response.get("body", {})
            choices = body.get("choices", [])
            content = choices[0]["message"]["content"] if choices else ""

            usage = body.get("usage", {})
            prompt_tokens += usage.get("prompt_tokens", 0)
            completion_tokens += usage.get("completion_tokens", 0)
            successful_items += 1

            results[cid] = {"status": "success", "content": content}

        rates = cls.STANDARD_RATES.get(model, cls.STANDARD_RATES["gpt-4o-mini"])
        std_cost = (prompt_tokens * rates["prompt"]) + (completion_tokens * rates["completion"])
        batch_cost = std_cost * 0.50  # 50% discount on OpenAI and Anthropic Batch APIs
        savings = std_cost - batch_cost

        summary = CostSummary(
            total_prompt_tokens=prompt_tokens,
            total_completion_tokens=completion_tokens,
            standard_cost_usd=round(std_cost, 6),
            batch_discounted_cost_usd=round(batch_cost, 6),
            net_savings_usd=round(savings, 6),
            successful_items=successful_items,
            failed_items=failed_items,
        )

        return results, summary

