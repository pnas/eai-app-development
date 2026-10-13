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


def test_gemini_cache_threshold_audit():
    """Verify context caching threshold logic per Gemini Enterprise Agent Platform specs."""
    # Gemini 2 family requires >= 2,048 tokens
    assert not OptimizedPromptBuilder.is_gemini_cache_eligible(1500, model="gemini-2.5-flash")
    assert OptimizedPromptBuilder.is_gemini_cache_eligible(2048, model="gemini-2.5-flash")
    assert OptimizedPromptBuilder.is_gemini_cache_eligible(2500, model="gemini-2.5-pro")

    # Gemini 3 family requires >= 4,096 tokens
    assert not OptimizedPromptBuilder.is_gemini_cache_eligible(2048, model="gemini-3-flash")
    assert OptimizedPromptBuilder.is_gemini_cache_eligible(4096, model="gemini-3-flash")
    assert OptimizedPromptBuilder.is_gemini_cache_eligible(5000, model="gemini-3.1-pro")

    # Gemini 3 implicit preview models (e.g. 3.7 Flash, 3.8 Flash) require >= 6,144 tokens
    assert not OptimizedPromptBuilder.is_gemini_cache_eligible(5000, model="gemini-3.7-flash")
    assert OptimizedPromptBuilder.is_gemini_cache_eligible(6144, model="gemini-3.7-flash")
    assert OptimizedPromptBuilder.is_gemini_cache_eligible(7000, model="gemini-3.8-flash")


def test_anthropic_cache_threshold_audit():
    """Verify Anthropic caching limits (Sonnet/Opus >= 1024, Haiku >= 2048)."""
    # Claude 5.5, 3.7 & 3.5 Sonnet / Opus
    assert not OptimizedPromptBuilder.is_anthropic_cache_eligible(1000, model="claude-sonnet-5-5")
    assert OptimizedPromptBuilder.is_anthropic_cache_eligible(1024, model="claude-sonnet-5-5")
    assert OptimizedPromptBuilder.is_anthropic_cache_eligible(1024, model="claude-opus-5-5")
    assert not OptimizedPromptBuilder.is_anthropic_cache_eligible(1000, model="claude-3-7-sonnet-20250219")
    assert OptimizedPromptBuilder.is_anthropic_cache_eligible(1024, model="claude-3-7-sonnet-20250219")
    assert OptimizedPromptBuilder.is_anthropic_cache_eligible(1024, model="claude-3-5-sonnet-20241022")

    # Claude Haiku
    assert not OptimizedPromptBuilder.is_anthropic_cache_eligible(1024, model="claude-haiku-5-5")
    assert OptimizedPromptBuilder.is_anthropic_cache_eligible(2048, model="claude-haiku-5-5")
    assert not OptimizedPromptBuilder.is_anthropic_cache_eligible(1024, model="claude-3-5-haiku-20241022")
    assert not OptimizedPromptBuilder.is_anthropic_cache_eligible(2000, model="claude-3-haiku-20240307")
    assert OptimizedPromptBuilder.is_anthropic_cache_eligible(2048, model="claude-3-5-haiku-20241022")


def test_openai_cache_threshold_audit():
    """Verify OpenAI automatic prefix caching threshold (>= 1024 tokens)."""
    assert not OptimizedPromptBuilder.is_openai_cache_eligible(1000, model="gpt-4o")
    assert not OptimizedPromptBuilder.is_openai_cache_eligible(1023, model="gpt-4o-mini")
    assert OptimizedPromptBuilder.is_openai_cache_eligible(1024, model="gpt-4o")
    assert OptimizedPromptBuilder.is_openai_cache_eligible(2048, model="o1")
    assert OptimizedPromptBuilder.is_openai_cache_eligible(1024, model="o3-mini")


def test_anthropic_breakpoint_audit():
    """Verify Anthropic breakpoint counting across system, tools, and messages."""
    payload = {
        "model": "claude-3-7-sonnet-20250219",
        "system": [
            {"type": "text", "text": "Policy 1", "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": "Policy 2"},
        ],
        "tools": [
            {"name": "t1", "description": "d1", "cache_control": {"type": "ephemeral"}},
            {"name": "t2", "description": "d2"},
        ],
        "messages": [
            {"role": "user", "content": [{"type": "text", "text": "q1", "cache_control": {"type": "ephemeral"}}]},
            {"role": "assistant", "content": "a1"},
            {"role": "user", "content": "q2"},
        ],
    }
    count = OptimizedPromptBuilder.count_anthropic_breakpoints(payload)
    assert count == 3, f"Expected 3 breakpoints, got {count}"
    assert count <= OptimizedPromptBuilder.MAX_ANTHROPIC_BREAKPOINTS


def test_diagnose_cache_miss_taxonomy(sample_kb, sample_tools_1, sample_tools_2):
    """Verify diagnose_cache_miss reproduces OpenAI's diagnostics reasons taxonomy."""
    base = OptimizedPromptBuilder.build_optimized_payload(sample_kb, sample_tools_1, "Ticket")
    base["prompt_cache_key"] = "tenant-telekom-prod"
    base["reasoning_effort"] = "medium"

    # 1. Exact match -> cache_hit
    hit_payload = OptimizedPromptBuilder.build_optimized_payload(sample_kb, sample_tools_1, "Another Ticket")
    hit_payload["prompt_cache_key"] = "tenant-telekom-prod"
    hit_payload["reasoning_effort"] = "medium"
    diag = OptimizedPromptBuilder.diagnose_cache_miss(base, hit_payload)
    assert diag["type"] == "cache_hit"
    assert diag["reason"] is None

    # 2. Model changed
    m_payload = dict(hit_payload)
    m_payload["model"] = "claude-3-5-sonnet-20241022"
    diag = OptimizedPromptBuilder.diagnose_cache_miss(base, m_payload)
    assert diag["type"] == "cache_miss"
    assert diag["reason"] == "model_changed"

    # 3. Prompt cache key changed
    k_payload = dict(hit_payload)
    k_payload["prompt_cache_key"] = "tenant-telekom-staging"
    diag = OptimizedPromptBuilder.diagnose_cache_miss(base, k_payload)
    assert diag["type"] == "cache_miss"
    assert diag["reason"] == "prompt_cache_key_changed"

    # 4. Reasoning effort changed
    r_payload = dict(hit_payload)
    r_payload["reasoning_effort"] = "high"
    diag = OptimizedPromptBuilder.diagnose_cache_miss(base, r_payload)
    assert diag["type"] == "cache_miss"
    assert diag["reason"] == "reasoning_effort_changed"

    # 5. Tools changed
    t_payload = dict(hit_payload)
    t_payload["tools"] = [{"name": "different_tool", "description": "desc"}]
    diag = OptimizedPromptBuilder.diagnose_cache_miss(base, t_payload)
    assert diag["type"] == "cache_miss"
    assert diag["reason"] == "tools_changed"

    # 6. Input prefix changed
    i_payload = dict(hit_payload)
    i_payload["system"] = [{"type": "text", "text": "Mutated prefix text"}]
    diag = OptimizedPromptBuilder.diagnose_cache_miss(base, i_payload)
    assert diag["type"] == "cache_miss"
    assert diag["reason"] == "input_changed"


def test_anthropic_diagnostics_taxonomy(sample_kb, sample_tools_1):
    """Verify diagnose_cache_miss reproduces Anthropic's Cache Diagnostics reasons taxonomy."""
    base = OptimizedPromptBuilder.build_optimized_payload(sample_kb, sample_tools_1, "Ticket")
    base["id"] = "msg_0123456789abcdef"
    base["messages"] = [
        {"role": "user", "content": "What is the policy?"},
        {"role": "assistant", "content": "The policy requires 15m response."},
    ]

    # 1. Exact match / subsequent turn -> cache_hit
    hit_payload = dict(base)
    hit_payload["previous_message_id"] = "msg_0123456789abcdef"
    hit_payload["messages"] = base["messages"] + [{"role": "user", "content": "Follow-up question"}]
    diag = OptimizedPromptBuilder.diagnose_cache_miss(base, hit_payload, provider="anthropic")
    assert diag["type"] == "cache_hit"
    assert diag["reason"] is None

    # 2. system_changed
    sys_payload = dict(hit_payload)
    sys_payload["system"] = [{"type": "text", "text": "Mutated system instructions", "cache_control": {"type": "ephemeral"}}]
    diag = OptimizedPromptBuilder.diagnose_cache_miss(base, sys_payload, provider="anthropic")
    assert diag["type"] == "cache_miss"
    assert diag["reason"] == "system_changed"
    assert diag.get("cache_missed_input_tokens", 0) > 0

    # 3. messages_changed (prior history altered)
    msg_payload = dict(hit_payload)
    msg_payload["messages"] = [{"role": "user", "content": "Rewritten history"}]
    diag = OptimizedPromptBuilder.diagnose_cache_miss(base, msg_payload, provider="anthropic")
    assert diag["type"] == "cache_miss"
    assert diag["reason"] == "messages_changed"
    assert diag.get("cache_missed_input_tokens", 0) > 0

    # 4. tools_changed
    tools_payload = dict(hit_payload)
    tools_payload["tools"] = [{"name": "new_tool", "description": "New schema"}]
    diag = OptimizedPromptBuilder.diagnose_cache_miss(base, tools_payload, provider="anthropic")
    assert diag["type"] == "cache_miss"
    assert diag["reason"] == "tools_changed"
    assert diag.get("cache_missed_input_tokens", 0) > 0

    # 5. previous_message_not_found
    missing_payload = dict(hit_payload)
    missing_payload["previous_message_id"] = "msg_expired_or_invalid"
    diag = OptimizedPromptBuilder.diagnose_cache_miss(base, missing_payload, provider="anthropic")
    assert diag["type"] == "cache_miss"
    assert diag["reason"] == "previous_message_not_found"


def test_anthropic_extended_ttl_and_top_level_cache(sample_kb, sample_tools_1):
    """Verify 1-hour extended TTL support and top-level automatic cache breakpoint counting."""
    # 1. Extended 1h TTL on system block
    payload_1h = OptimizedPromptBuilder.build_optimized_payload(
        sample_kb, sample_tools_1, "Ticket", ttl="1h"
    )
    assert payload_1h["system"][0]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}

    # 2. Top-level automatic caching consumes 1 breakpoint slot
    top_level_payload = {
        "model": "claude-3-7-sonnet-20250219",
        "cache_control": {"type": "ephemeral"},  # <-- Top-level automatic caching
        "system": [
            {"type": "text", "text": "Policy 1", "cache_control": {"type": "ephemeral"}},
        ],
        "messages": [
            {"role": "user", "content": "Hello"},
        ],
    }
    count = OptimizedPromptBuilder.count_anthropic_breakpoints(top_level_payload)
    assert count == 2, f"Expected 2 breakpoints (1 top-level + 1 system), got {count}"


