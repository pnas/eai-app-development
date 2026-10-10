"""Core Model Factory for LangChain & LangGraph Integrations.

Provides unified, type-safe creation of ChatOpenAI, ChatAnthropic,
and ChatGoogleGenerativeAI models with normalized configuration,
streaming support, and resilient fallback cascades.
"""

from __future__ import annotations

import os
from typing import Any, List, Optional
from dotenv import load_dotenv

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()


def get_chat_model(
    provider: str = "openai",
    model: Optional[str] = None,
    temperature: float = 0.0,
    streaming: bool = True,
    **kwargs: Any,
) -> BaseChatModel:
    """Instantiate a normalized ChatModel across OpenAI, Anthropic, or Gemini.

    Args:
        provider: 'openai', 'anthropic', or 'gemini'
        model: Specific model name (falls back to sensible defaults)
        temperature: Sampling temperature (0.0 for deterministic output)
        streaming: Enable token streaming
        **kwargs: Additional provider-specific arguments
    """
    provider_lower = provider.lower()

    if provider_lower in ("openai", "open_ai"):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is missing.")
        return ChatOpenAI(
            model=model or "gpt-4o-mini",
            temperature=temperature,
            streaming=streaming,
            api_key=api_key,
            **kwargs,
        )

    elif provider_lower in ("anthropic", "claude"):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is missing.")
        return ChatAnthropic(
            model=model or "claude-3-5-haiku-20241022",
            temperature=temperature,
            streaming=streaming,
            api_key=api_key,
            **kwargs,
        )

    elif provider_lower in ("gemini", "google", "google-genai"):
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is missing.")
        return ChatGoogleGenerativeAI(
            model=model or "gemini-2.0-flash",
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
) -> BaseChatModel:
    """Constructs a 3-tier fallback cascade via LangChain's .with_fallbacks().

    Flow: Primary -> Secondary -> Tertiary
    """
    primary = get_chat_model(primary_provider, temperature=temperature)
    secondary = get_chat_model(secondary_provider, temperature=temperature)
    tertiary = get_chat_model(tertiary_provider, temperature=temperature)

    return primary.with_fallbacks([secondary, tertiary])

