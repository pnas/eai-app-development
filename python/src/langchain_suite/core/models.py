"""Core Model Factory for LangChain & LangGraph Integrations.

Provides unified, type-safe creation of ChatOpenAI, ChatAnthropic,
and ChatGoogleGenerativeAI models with normalized configuration,
streaming support, parameter constraint handling, and resilient fallback cascades.

Reference:
- docs/api_comparison_matrix.md
- https://platform.claude.com/docs/en/build-with-claude/working-with-messages
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from src.langchain_suite.core.env import load_workspace_env

load_workspace_env()

# Canonical Default Models (Table 1: Primary Models as of 2026)
DEFAULT_MODELS: Dict[str, str] = {
    "openai": "gpt-4.1-mini",
    "anthropic": "claude-haiku-5-5",
    "gemini": "gemini-3.8-flash",
}

# Provider Model Catalog matching docs/api_comparison_matrix.md
PRIMARY_MODELS: Dict[str, Dict[str, List[str]]] = {
    "openai": {
        "flagship_reasoning": ["gpt-6-astra", "gpt-6.1-sol"],
        "fast_reasoning": ["gpt-6-luna"],
        "high_throughput": ["gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano"],
        "legacy": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-4"],
    },
    "anthropic": {
        "flagship": ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"],
        "specialized": ["claude-opus-5", "claude-fable-5-1", "claude-mythos-5-1"],
        "v4_5_class": ["claude-opus-4-5", "claude-sonnet-4-5", "claude-haiku-4-5"],
        "legacy": ["claude-3-7-sonnet", "claude-3-5-sonnet", "claude-3-5-haiku"],
    },
    "gemini": {
        "flagship": ["gemini-3.8-flash"],
        "high_throughput": ["gemini-3.5-flash-lite"],
        "frontier": ["gemini-3.1-pro-preview"],
        "live": ["gemini-3.8-live", "gemini-3.8-live-extended-thinking"],
        "legacy": ["gemini-2.5-pro", "gemini-2.0-flash"],
    },
}


def is_reasoning_model(model_name: str) -> bool:
    """Detects if an OpenAI model is a dedicated reasoning model (gpt-6*, o1*, o3*, o4*).
    
    Reasoning models do not accept standard temperature=0.0 and require fixed/omitted temperature.
    """
    m = model_name.lower().strip()
    return any(m.startswith(prefix) for prefix in ("gpt-6", "o1", "o3", "o4")) or "-reasoning" in m


def is_sampling_restricted_anthropic(model_name: str) -> bool:
    """Detects if an Anthropic model prohibits sampling parameters (temperature, top_p, top_k).
    
    Per 2026 specs in docs/api_comparison_matrix.md:
    - Claude 4.7+ and Claude 5.x return HTTP 400 if temperature/top_p/top_k are supplied.
    - Claude 4.5 class (opus-4-5, sonnet-4-5, haiku-4-5) and 3.x support temperature.
    """
    m = model_name.lower().strip()
    # Explicitly allow claude-3-x and claude-4-5 / claude-4.5
    if "claude-3" in m or "4-5" in m or "4.5" in m:
        return False
    
    # Check for Claude 5.x or Claude 4.7+
    import re
    if re.search(r'claude-(opus|sonnet|haiku|fable|mythos)?-?5[-.]', m):
        return True
    if any(p in m for p in ("-5-5", "-5.5", "-5-1", "-5.1", "-4-7", "-4.7", "opus-5", "sonnet-5", "haiku-5")):
        return True
    return False


def get_chat_model(
    provider: str = "openai",
    model: Optional[str] = None,
    temperature: float = 0.0,
    streaming: bool = True,
    **kwargs: Any,
) -> BaseChatModel:
    """Instantiate a normalized ChatModel across OpenAI, Anthropic, or Gemini.

    Normalizes provider configuration, handles reasoning model restrictions,
    respects Claude 5.x sampling constraints, and supports all legacy and frontier models.

    Args:
        provider: 'openai', 'anthropic', or 'gemini'
        model: Specific model name (defaults to modern 2026 flagship/high-throughput)
        temperature: Sampling temperature (0.0 for deterministic output where supported)
        streaming: Enable token streaming
        **kwargs: Additional provider-specific arguments
    """
    provider_lower = provider.strip().lower()

    if provider_lower in ("openai", "open_ai"):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is missing.")
        
        model_name = model or DEFAULT_MODELS["openai"]
        openai_kwargs = dict(kwargs)

        # Reasoning models (gpt-6*, o1*, o3*) do not accept temperature=0.0
        if not is_reasoning_model(model_name):
            openai_kwargs["temperature"] = temperature

        return ChatOpenAI(
            model=model_name,
            streaming=streaming,
            api_key=api_key,
            **openai_kwargs,
        )

    elif provider_lower in ("anthropic", "claude"):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is missing.")
        
        model_name = model or DEFAULT_MODELS["anthropic"]
        anthropic_kwargs = dict(kwargs)

        # On Claude 4.7+ and 5.x, temperature/top_p causes HTTP 400
        # On Claude 4.5 class and 3.x, temperature is fully supported
        if not is_sampling_restricted_anthropic(model_name):
            anthropic_kwargs["temperature"] = temperature

        return ChatAnthropic(
            model=model_name,
            streaming=streaming,
            api_key=api_key,
            **anthropic_kwargs,
        )

    elif provider_lower in ("gemini", "google", "google-genai"):
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is missing.")
        
        model_name = model or DEFAULT_MODELS["gemini"]
        return ChatGoogleGenerativeAI(
            model=model_name,
            temperature=temperature,
            streaming=streaming,
            google_api_key=api_key,
            **kwargs,
        )

    raise ValueError(f"Unsupported provider: '{provider}'. Choose 'openai', 'anthropic', or 'gemini'.")


def get_resilient_cascade(
    primary_provider: str = "anthropic",
    secondary_provider: str = "openai",
    tertiary_provider: str = "gemini",
    temperature: float = 0.0,
    primary_model: Optional[str] = None,
    secondary_model: Optional[str] = None,
    tertiary_model: Optional[str] = None,
) -> BaseChatModel:
    """Constructs a 3-tier fallback cascade via LangChain's .with_fallbacks().

    Modern 2026 Cascade:
    Primary (Claude Haiku 5.5) -> Secondary (GPT-4.1-mini) -> Tertiary (Gemini 3.8 Flash)
    """
    primary = get_chat_model(primary_provider, model=primary_model, temperature=temperature)
    secondary = get_chat_model(secondary_provider, model=secondary_model, temperature=temperature)
    tertiary = get_chat_model(tertiary_provider, model=tertiary_model, temperature=temperature)

    return primary.with_fallbacks([secondary, tertiary])
