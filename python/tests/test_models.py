"""Unit tests for the unified LangChain model factory and frontier model mappings."""

from __future__ import annotations

import os
from unittest.mock import patch
import pytest

from src.langchain_suite.core.models import (
    DEFAULT_MODELS,
    PRIMARY_MODELS,
    is_reasoning_model,
    is_sampling_restricted_anthropic,
    get_chat_model,
    get_resilient_cascade,
)


def test_default_models_are_frontier():
    """Verify DEFAULT_MODELS points to the latest generation frontier models."""
    assert DEFAULT_MODELS["openai"] == "gpt-4.1-mini"
    assert DEFAULT_MODELS["anthropic"] == "claude-haiku-5-5"
    assert DEFAULT_MODELS["gemini"] == "gemini-3.8-flash"


def test_is_reasoning_model():
    """Verify reasoning model detection across gpt-6*, o1*, o3*, o4* vs standard models."""
    # Reasoning models
    assert is_reasoning_model("gpt-6-astra") is True
    assert is_reasoning_model("gpt-6.1-sol") is True
    assert is_reasoning_model("gpt-6-luna") is True
    assert is_reasoning_model("o1-preview") is True
    assert is_reasoning_model("o3-mini") is True
    assert is_reasoning_model("o4-mini") is True

    # Standard models (must allow temperature)
    assert is_reasoning_model("gpt-4.1-mini") is False
    assert is_reasoning_model("gpt-4.1") is False
    assert is_reasoning_model("gpt-4o") is False
    assert is_reasoning_model("gpt-4o-mini") is False
    assert is_reasoning_model("gpt-4-turbo") is False


def test_is_sampling_restricted_anthropic():
    """Verify Anthropic temperature restriction detection (Claude 4.7+, 5.x vs 4.5, 3.x)."""
    # Restricted sampling models (Claude 4.7+, 5.x)
    assert is_sampling_restricted_anthropic("claude-opus-5-5") is True
    assert is_sampling_restricted_anthropic("claude-sonnet-5-5") is True
    assert is_sampling_restricted_anthropic("claude-haiku-5-5") is True
    assert is_sampling_restricted_anthropic("claude-fable-5-1") is True
    assert is_sampling_restricted_anthropic("claude-mythos-5-1") is True
    assert is_sampling_restricted_anthropic("claude-opus-4.7") is True

    # Models that accept temperature (Claude 4.5, 3.x)
    assert is_sampling_restricted_anthropic("claude-opus-4-5") is False
    assert is_sampling_restricted_anthropic("claude-sonnet-4-5") is False
    assert is_sampling_restricted_anthropic("claude-haiku-4-5") is False
    assert is_sampling_restricted_anthropic("claude-3-5-sonnet-20241022") is False
    assert is_sampling_restricted_anthropic("claude-3-opus-20240229") is False


@patch.dict(os.environ, {"OPENAI_API_KEY": "sk-mock-key-12345"})
def test_openai_model_instantiation_standard_vs_reasoning():
    """Verify standard OpenAI models retain temperature while reasoning models omit it."""
    # Standard model: temperature should be set
    m_std = get_chat_model("openai", model="gpt-4.1-mini", temperature=0.2)
    assert m_std.model_name == "gpt-4.1-mini"
    assert m_std.temperature == 0.2

    # Legacy gpt-4 model
    m_legacy = get_chat_model("openai", model="gpt-4-turbo", temperature=0.7)
    assert m_legacy.model_name == "gpt-4-turbo"
    assert m_legacy.temperature == 0.7

    # Reasoning model: temperature should be None (stripped)
    m_reasoning = get_chat_model("openai", model="gpt-6-astra", temperature=0.7)
    assert m_reasoning.model_name == "gpt-6-astra"
    assert m_reasoning.temperature is None


@patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-mock-key-12345"})
def test_anthropic_model_instantiation_standard_vs_restricted():
    """Verify Claude 4.5 retains temperature while Claude 5.x / restricted omits it."""
    # Claude 4.5: supports temperature
    m_45 = get_chat_model("anthropic", model="claude-sonnet-4-5", temperature=0.3)
    assert m_45.model == "claude-sonnet-4-5"
    assert m_45.temperature == 0.3

    # Claude 5.5: temperature must be stripped
    m_55 = get_chat_model("anthropic", model="claude-haiku-5-5", temperature=0.5)
    assert m_55.model == "claude-haiku-5-5"
    assert m_55.temperature is None


@patch.dict(os.environ, {"GEMINI_API_KEY": "mock-gemini-key-12345"})
def test_gemini_model_instantiation():
    """Verify Gemini models instantiate correctly with legacy and latest versions."""
    # Latest frontier
    m_latest = get_chat_model("gemini", model="gemini-3.8-flash", temperature=0.4)
    assert m_latest.model == "gemini-3.8-flash"
    assert m_latest.temperature == 0.4

    # Preview / 3.1 class
    m_preview = get_chat_model("gemini", model="gemini-3.1-pro-preview", temperature=0.1)
    assert m_preview.model == "gemini-3.1-pro-preview"
    assert m_preview.temperature == 0.1


@patch.dict(os.environ, {
    "OPENAI_API_KEY": "sk-mock-key",
    "ANTHROPIC_API_KEY": "sk-ant-mock-key",
    "GEMINI_API_KEY": "mock-gemini-key",
})
def test_resilient_cascade_construction():
    """Verify resilient fallback cascade constructs cleanly across provider tiers."""
    cascade = get_resilient_cascade(
        primary_provider="openai",
        primary_model="gpt-4.1-mini",
        secondary_provider="anthropic",
        tertiary_provider="gemini",
    )
    assert cascade is not None
