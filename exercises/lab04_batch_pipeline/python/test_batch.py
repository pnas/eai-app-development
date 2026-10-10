"""Test suite for Lab 04: Batch API Cost Arbitrage Pipeline."""

import json
import sys
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parents[3]
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import pytest
from exercises.lab04_batch_pipeline.python.solution import BatchPipeline


def test_generate_batch_jsonl():
    items = [
        {"id": "req-001", "prompt": "Summarize transcript 1"},
        {"id": "req-002", "prompt": "Extract entities from transcript 2"},
    ]

    jsonl_output = BatchPipeline.generate_batch_jsonl(items, model="gpt-4o-mini")
    lines = jsonl_output.strip().split("\n")
    assert len(lines) == 2

    parsed_0 = json.loads(lines[0])
    assert parsed_0["custom_id"] == "req-001"
    assert parsed_0["method"] == "POST"
    assert parsed_0["url"] == "/v1/chat/completions"
    assert parsed_0["body"]["messages"][0]["content"] == "Summarize transcript 1"


def test_process_batch_results_mixed_success_and_errors():
    mock_results_jsonl = "\n".join([
        json.dumps({
            "custom_id": "req-001",
            "response": {
                "status_code": 200,
                "body": {
                    "choices": [{"message": {"content": "Summary result 1"}}],
                    "usage": {"prompt_tokens": 1000, "completion_tokens": 200},
                },
            },
            "error": None,
        }),
        json.dumps({
            "custom_id": "req-002",
            "response": None,
            "error": {"code": "content_policy_violation", "message": "Triggered safety filter"},
        }),
        json.dumps({
            "custom_id": "req-003",
            "response": {
                "status_code": 200,
                "body": {
                    "choices": [{"message": {"content": "Summary result 3"}}],
                    "usage": {"prompt_tokens": 3000, "completion_tokens": 800},
                },
            },
            "error": None,
        }),
    ])

    results, summary = BatchPipeline.process_batch_results(mock_results_jsonl, model="gpt-4o-mini")

    assert summary.successful_items == 2
    assert summary.failed_items == 1
    assert summary.total_prompt_tokens == 4000
    assert summary.total_completion_tokens == 1000

    # Test line isolation
    assert results["req-001"]["status"] == "success"
    assert results["req-001"]["content"] == "Summary result 1"
    assert results["req-002"]["status"] == "error"
    assert "content_policy_violation" in results["req-002"]["error"]["code"]
    assert results["req-003"]["status"] == "success"

    # Test financial 50% arbitrage
    # Rates: prompt = 0.15 / 1M, completion = 0.60 / 1M
    # 4000 * 0.15/1M = 0.0006
    # 1000 * 0.60/1M = 0.0006
    # Total std = 0.0012
    # Batch cost = 0.0006
    assert summary.standard_cost_usd == pytest.approx(0.0012, rel=1e-4)
    assert summary.batch_discounted_cost_usd == pytest.approx(0.0006, rel=1e-4)
    assert summary.net_savings_usd == pytest.approx(0.0006, rel=1e-4)

