"""Lab 02 Reference Solution: Prompt Cache Optimization & Audit."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List


class OptimizedPromptBuilder:
    """Fixed prompt builder that guarantees cache hits."""

    # Anthropic Claude limits
    MIN_ANTHROPIC_CACHE_TOKENS = 1024
    MIN_ANTHROPIC_HAIKU_CACHE_TOKENS = 2048
    MAX_ANTHROPIC_BREAKPOINTS = 4

    # OpenAI limits
    MIN_OPENAI_CACHE_TOKENS = 1024

    # Google Gemini Enterprise Agent Platform context caching limits
    MIN_GEMINI_2_CACHE_TOKENS = 2048
    MIN_GEMINI_3_CACHE_TOKENS = 4096
    MIN_GEMINI_3_IMPLICIT_PREVIEW_TOKENS = 6144

    @classmethod
    def estimate_tokens(cls, text: str) -> int:
        """Rough estimation: ~4 characters per token."""
        return len(text) // 4

    @classmethod
    def is_anthropic_cache_eligible(
        cls,
        token_count: int,
        model: str = "claude-3-7-sonnet-20250219",
    ) -> bool:
        """Verify token count against Anthropic prompt caching limits."""
        m = model.lower()
        if "haiku" in m:
            return token_count >= cls.MIN_ANTHROPIC_HAIKU_CACHE_TOKENS
        return token_count >= cls.MIN_ANTHROPIC_CACHE_TOKENS

    @classmethod
    def is_openai_cache_eligible(
        cls,
        token_count: int,
        model: str = "gpt-4o",
    ) -> bool:
        """Verify token count against OpenAI automatic prefix caching limits."""
        return token_count >= cls.MIN_OPENAI_CACHE_TOKENS

    @classmethod
    def count_anthropic_breakpoints(cls, payload: Dict[str, Any]) -> int:
        """Count total cache_control breakpoints across top-level, system, tools, and messages."""
        count = 0
        # Check top-level request automatic cache_control
        if isinstance(payload.get("cache_control"), dict):
            count += 1
        # Check system blocks
        for block in payload.get("system", []):
            if isinstance(block, dict) and "cache_control" in block:
                count += 1
        # Check tool definitions
        for tool in payload.get("tools", []):
            if isinstance(tool, dict) and "cache_control" in tool:
                count += 1
        # Check messages
        for msg in payload.get("messages", []):
            if isinstance(msg, dict):
                content = msg.get("content")
                if isinstance(content, list):
                    for part in content:
                        if isinstance(part, dict) and "cache_control" in part:
                            count += 1
                elif "cache_control" in msg:
                    count += 1
        return count

    @classmethod
    def is_gemini_cache_eligible(
        cls,
        token_count: int,
        model: str = "gemini-2.5-flash",
        implicit_preview: bool = False,
    ) -> bool:
        """Verify token count against Gemini Enterprise Agent Platform context caching limits."""
        m = model.lower()
        if "gemini-3" in m or "gemini-3." in m:
            if implicit_preview or any(p in m for p in ["3.0-flash-preview", "3.1-pro-preview", "3.7-flash", "3.8-flash"]):
                return token_count >= cls.MIN_GEMINI_3_IMPLICIT_PREVIEW_TOKENS
            return token_count >= cls.MIN_GEMINI_3_CACHE_TOKENS
        return token_count >= cls.MIN_GEMINI_2_CACHE_TOKENS

    @classmethod
    def build_optimized_payload(
        cls,
        documentation_kb: str,
        tools_config: Dict[str, Any],
        user_ticket: str,
        timestamp: str | None = None,
        ttl: str = "5m",
    ) -> Dict[str, Any]:
        """Build an Anthropic/OpenAI prompt payload that maximizes prompt cache hits.

        1. Deterministically sort JSON tools config.
        2. Combine static documentation + tools.
        3. Ensure the static block meets the 1,024 minimum token threshold.
        4. Place cache_control: {"type": "ephemeral", "ttl": ...} on the static block.
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

        cache_control_obj: Dict[str, Any] = {"type": "ephemeral"}
        if ttl and ttl != "5m":
            cache_control_obj["ttl"] = ttl

        return {
            "model": "claude-3-7-sonnet-20250219",
            "system": [
                {
                    "type": "text",
                    "text": static_prefix,
                    "cache_control": cache_control_obj,
                }
            ],
            "messages": [
                {
                    "role": "user",
                    "content": dynamic_user_content,
                }
            ],
        }


    @classmethod
    def diagnose_cache_miss(
        cls,
        baseline: Dict[str, Any],
        current: Dict[str, Any],
        provider: str = "auto",
    ) -> Dict[str, Any]:
        """Diagnose why two consecutive requests caused a cache miss or hit.

        Supports both:
        1. OpenAI Prompt Cache Diagnostics taxonomy:
           - model_changed, prompt_cache_key_changed, reasoning_effort_changed,
             tools_changed, input_changed
        2. Anthropic Cache Diagnostics taxonomy:
           - model_changed, system_changed, tools_changed, messages_changed,
             previous_message_not_found, unavailable
           - Includes estimated cache_missed_input_tokens
        """
        is_anthropic = provider == "anthropic" or (
            provider == "auto"
            and any(
                str(m).lower().startswith("claude")
                for m in [baseline.get("model"), current.get("model")]
                if m
            )
            and ("prompt_cache_key" not in baseline and "reasoning_effort" not in baseline)
        )

        # 1. Model changed (common to both)
        if baseline.get("model") != current.get("model"):
            res: Dict[str, Any] = {"type": "cache_miss", "reason": "model_changed"}
            if is_anthropic:
                res["cache_missed_input_tokens"] = cls.estimate_tokens(str(current.get("system", "")) + str(current.get("messages", "")))
            return res

        # 2. Anthropic previous_message_id check
        if is_anthropic and "previous_message_id" in current:
            baseline_id = baseline.get("id") or baseline.get("response_id")
            if current["previous_message_id"] != baseline_id:
                return {
                    "type": "cache_miss",
                    "reason": "previous_message_not_found",
                    "cache_missed_input_tokens": cls.estimate_tokens(str(current.get("system", "")) + str(current.get("messages", ""))),
                }

        # 3. OpenAI specific routing and configuration
        if not is_anthropic:
            if baseline.get("prompt_cache_key") != current.get("prompt_cache_key"):
                return {"type": "cache_miss", "reason": "prompt_cache_key_changed"}

            if baseline.get("reasoning_effort") != current.get("reasoning_effort"):
                return {"type": "cache_miss", "reason": "reasoning_effort_changed"}

        # 4. Tools changed (common to both)
        b_tools = json.dumps(baseline.get("tools"), sort_keys=True) if baseline.get("tools") else None
        c_tools = json.dumps(current.get("tools"), sort_keys=True) if current.get("tools") else None
        if b_tools != c_tools:
            res = {"type": "cache_miss", "reason": "tools_changed"}
            if is_anthropic:
                res["cache_missed_input_tokens"] = cls.estimate_tokens(str(current.get("tools", "")))
            return res

        # 5. System prompt changed
        b_system_hash = compute_prefix_hash(baseline.get("system", []))
        c_system_hash = compute_prefix_hash(current.get("system", []))
        if b_system_hash != c_system_hash:
            if is_anthropic:
                missed = cls.estimate_tokens(str(current.get("system", "")))
                return {"type": "cache_miss", "reason": "system_changed", "cache_missed_input_tokens": missed}
            return {"type": "cache_miss", "reason": "input_changed"}

        # 6. Messages history changed (Anthropic fine-grained audit)
        if is_anthropic:
            b_msgs = json.dumps(baseline.get("messages", []))
            c_msgs = json.dumps(current.get("messages", []))
            # If current does not preserve baseline messages prefix, messages changed
            if not c_msgs.startswith(b_msgs[:-1] if len(b_msgs) > 2 else "["):
                missed = cls.estimate_tokens(str(current.get("messages", "")))
                return {"type": "cache_miss", "reason": "messages_changed", "cache_missed_input_tokens": missed}

        return {"type": "cache_hit", "reason": None}


def compute_prefix_hash(system_blocks: Any) -> str:
    """Simulate provider prefix hashing algorithm to test cache hit/miss."""
    if isinstance(system_blocks, str):
        return hashlib.sha256(system_blocks.encode("utf-8")).hexdigest()
    concatenated = ""
    for block in system_blocks:
        if isinstance(block, dict):
            concatenated += block.get("text", "")
            if block.get("cache_control"):
                break
        elif isinstance(block, str):
            concatenated += block
    return hashlib.sha256(concatenated.encode("utf-8")).hexdigest()

