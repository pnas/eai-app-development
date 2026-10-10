"""Lab 02 Reference Solution: Prompt Cache Optimization & Audit."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List


class OptimizedPromptBuilder:
    """Fixed prompt builder that guarantees cache hits."""

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

        1. Deterministically sort JSON tools config.
        2. Combine static documentation + tools.
        3. Ensure the static block meets the 1,024 minimum token threshold.
        4. Place cache_control: {"type": "ephemeral"} on the static block.
        5. Move dynamic time and user input into the user message block.
        """
        # Step 1: Deterministic JSON serialization
        sorted_tools = json.dumps(tools_config, sort_keys=True, separators=(",", ":"))

        # Step 2: Assemble static prefix
        static_prefix = (
            "### SYSTEM POLICIES & KNOWLEDGE BASE ###\n"
            f"{documentation_kb.strip()}\n\n"
            f"### AVAILABLE TOOL SPECS ###\n"
            f"{sorted_tools}"
        )

        # Step 3: Pad if below minimum cache threshold (1024 tokens ~ 4096 chars)
        current_tokens = cls.estimate_tokens(static_prefix)
        if current_tokens < cls.MIN_ANTHROPIC_CACHE_TOKENS:
            needed_tokens = cls.MIN_ANTHROPIC_CACHE_TOKENS - current_tokens + 50
            # Pad with clean instructions/documentation padding
            padding = "\n### EXTENDED CONTEXT GUIDELINES ###\n" + (
                "Ensure strict compliance with internal quality and security guidelines. "
                * (needed_tokens // 10)
            )
            static_prefix += padding

        # Step 4: Construct user payload with dynamic content (time + ticket)
        time_str = timestamp or "2026-10-10T00:00:00Z"
        dynamic_user_content = (
            f"[Current Timestamp: {time_str}]\n"
            f"User Ticket: {user_ticket}"
        )

        return {
            "model": "claude-3-7-sonnet-20250219",
            "system": [
                {
                    "type": "text",
                    "text": static_prefix,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            "messages": [
                {
                    "role": "user",
                    "content": dynamic_user_content,
                }
            ],
        }


def compute_prefix_hash(system_blocks: List[Dict[str, Any]]) -> str:
    """Simulate provider prefix hashing algorithm to test cache hit/miss."""
    concatenated = ""
    for block in system_blocks:
        concatenated += block.get("text", "")
        if block.get("cache_control"):
            break
    return hashlib.sha256(concatenated.encode("utf-8")).hexdigest()

