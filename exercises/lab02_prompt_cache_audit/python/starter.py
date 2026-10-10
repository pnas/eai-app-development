"""Lab 02 Starter: Prompt Cache Optimization & Audit.

Identify and repair the bugs breaking prompt caching.
"""

from __future__ import annotations

import datetime
import hashlib
import json
from typing import Any, Dict, List


class BrokenPromptBuilder:
    """The existing flawed prompt builder that produces 0% cache hits."""

    @staticmethod
    def build_payload(
        documentation_kb: str,
        tools_config: Dict[str, Any],
        user_ticket: str,
    ) -> Dict[str, Any]:
        # BUG 1: Dynamic timestamp at line 1 invalidates prefix hashing
        system_text = f"Current Time: {datetime.datetime.now().isoformat()}\n\n"
        system_text += documentation_kb

        # BUG 2: Unstable JSON serialization (random dict key ordering)
        tools_json = json.dumps(tools_config)

        # BUG 3 & 4: Ephemeral cache control placed on changing user message
        return {
            "model": "claude-3-7-sonnet-20250219",
            "system": [
                {
                    "type": "text",
                    "text": system_text + "\nTools: " + tools_json,
                }
            ],
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": user_ticket,
                            # Placing cache_control on dynamic user message is invalid
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                }
            ],
        }


class OptimizedPromptBuilder:
    """Student implementation: Fixed prompt builder that guarantees cache hits."""

    MIN_ANTHROPIC_CACHE_TOKENS = 1024

    @classmethod
    def estimate_tokens(cls, text: str) -> int:
        """Rough estimation: ~4 characters per token."""
        return len(text) // 4

    @classmethod
    def build_optimized_payload(
        cls,
        documentation_kb: str,
        tools_config: Dict[str, Any],
        user_ticket: str,
        timestamp: str | None = None,
    ) -> Dict[str, Any]:
        """Build an Anthropic/OpenAI prompt payload that maximizes prompt cache hits.

        Requirements:
        1. Static knowledge base must come FIRST in the system prompt.
        2. Tools config must be serialized with deterministic sorted keys.
        3. If the static prefix has fewer than 1024 estimated tokens, pad with
           neutral architectural context so Anthropic's cache threshold is met.
        4. Cache control breakpoint ({"type": "ephemeral"}) must be attached to
           the static system block, NOT the user message.
        5. Dynamic elements (timestamps, user ticket, session ID) must be placed
           in the user message or at the very end of the prompt.
        """
        # TODO: Implement the optimized prompt payload builder
        raise NotImplementedError("TODO: Implement build_optimized_payload")


def compute_prefix_hash(system_blocks: List[Dict[str, Any]]) -> str:
    """Simulate provider prefix hashing algorithm to test cache hit/miss."""
    # Serialize all text blocks marked with or preceding cache_control
    concatenated = ""
    for block in system_blocks:
        concatenated += block.get("text", "")
        if block.get("cache_control"):
            break
    return hashlib.sha256(concatenated.encode("utf-8")).hexdigest()

