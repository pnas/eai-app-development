"""Client factory for instantiating official SDK clients with validation."""

from __future__ import annotations

import os
from src.langchain_suite.core.env import load_workspace_env
import anthropic
import openai
from google import genai

# Load environment variables from .env
load_workspace_env()


def get_openai_client() -> openai.OpenAI:
    """Instantiate official OpenAI client."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("Missing OPENAI_API_KEY environment variable. Check .env")
    return openai.OpenAI(api_key=api_key)


def get_anthropic_client() -> anthropic.Anthropic:
    """Instantiate official Anthropic client."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("Missing ANTHROPIC_API_KEY environment variable. Check .env")
    return anthropic.Anthropic(api_key=api_key)


def get_gemini_client() -> genai.Client:
    """Instantiate official Google Gemini client (google-genai)."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Missing GEMINI_API_KEY environment variable. Check .env")
    return genai.Client(api_key=api_key)


def get_openrouter_client() -> openai.OpenAI:
    """Instantiate OpenRouter client using OpenAI-compatible SDK."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("Missing OPENROUTER_API_KEY environment variable. Check .env")
    return openai.OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        default_headers={
            "HTTP-Referer": "https://github.com/telekom/advanced-ai-integration",
            "X-Title": "Advanced AI Integration Course",
        },
    )

