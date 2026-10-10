"""Test suite for Lab 02: Prompt Cache Optimization & Audit."""

import sys
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parents[3]
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import pytest
from exercises.lab02_prompt_cache_audit.python.solution import (
    OptimizedPromptBuilder,
    compute_prefix_hash,
)
from exercises.lab02_prompt_cache_audit.python.starter import BrokenPromptBuilder


@pytest.fixture
def sample_kb():
    return "Standard Telecom SLA requires responding to P1 incidents within 15 minutes."


@pytest.fixture
def sample_tools_1():
    return {"b_tool": {"desc": "Restart modem"}, "a_tool": {"desc": "Check balance"}}


@pytest.fixture
def sample_tools_2():
    # Same dictionary but initialized in reverse order
    return {"a_tool": {"desc": "Check balance"}, "b_tool": {"desc": "Restart modem"}}


def test_broken_builder_produces_cache_misses(sample_kb, sample_tools_1):
    """Verify that BrokenPromptBuilder changes hash every call."""
    import time
    payload1 = BrokenPromptBuilder.build_payload(sample_kb, sample_tools_1, "Ticket 1")
    time.sleep(0.005)
    payload2 = BrokenPromptBuilder.build_payload(sample_kb, sample_tools_1, "Ticket 2")

    # In the broken builder, the system text has a dynamic datetime, so hashes differ
    hash1 = compute_prefix_hash(payload1["system"])
    hash2 = compute_prefix_hash(payload2["system"])
    assert hash1 != hash2, "Broken builder was expected to produce different hashes"


def test_optimized_builder_cache_hit_stability(sample_kb, sample_tools_1):
    """Verify that OptimizedPromptBuilder preserves exact prefix hash across tickets & times."""
    payload1 = OptimizedPromptBuilder.build_optimized_payload(
        sample_kb, sample_tools_1, "Customer cannot connect to 5G", timestamp="2026-10-10T10:00:00Z"
    )
    payload2 = OptimizedPromptBuilder.build_optimized_payload(
        sample_kb, sample_tools_1, "Billing query for invoice #999", timestamp="2026-10-10T10:05:00Z"
    )

    hash1 = compute_prefix_hash(payload1["system"])
    hash2 = compute_prefix_hash(payload2["system"])

    # Prefix hash MUST match 100%
    assert hash1 == hash2, "Prefix hashes must be identical for cache hits!"


def test_deterministic_tool_serialization(sample_kb, sample_tools_1, sample_tools_2):
    """Verify dictionary key insertion order does not invalidate cache hash."""
    payload1 = OptimizedPromptBuilder.build_optimized_payload(sample_kb, sample_tools_1, "Test")
    payload2 = OptimizedPromptBuilder.build_optimized_payload(sample_kb, sample_tools_2, "Test")

    hash1 = compute_prefix_hash(payload1["system"])
    hash2 = compute_prefix_hash(payload2["system"])

    assert hash1 == hash2, "Key order in tools config should not invalidate cache hash"


def test_minimum_token_threshold_met(sample_kb, sample_tools_1):
    """Verify static block meets Anthropic's 1024 token minimum threshold."""
    payload = OptimizedPromptBuilder.build_optimized_payload(sample_kb, sample_tools_1, "Ticket")
    system_text = payload["system"][0]["text"]
    estimated_tokens = OptimizedPromptBuilder.estimate_tokens(system_text)

    assert estimated_tokens >= 1024, f"Tokens ({estimated_tokens}) must meet >= 1024 threshold"


def test_cache_control_placement(sample_kb, sample_tools_1):
    """Verify cache_control is placed on system block and not on user message."""
    payload = OptimizedPromptBuilder.build_optimized_payload(sample_kb, sample_tools_1, "Ticket")

    assert "cache_control" in payload["system"][0]
    assert payload["system"][0]["cache_control"] == {"type": "ephemeral"}

    # User message must be a clean string or list without invalid cache_control
    user_msg = payload["messages"][0]["content"]
    assert isinstance(user_msg, str) or not any("cache_control" in b for b in user_msg if isinstance(b, dict))
