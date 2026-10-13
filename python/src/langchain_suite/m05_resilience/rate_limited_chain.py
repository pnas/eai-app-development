"""Module 5 (LangChain): Token-Aware Rate Limiting Runnable & Enterprise Governor.

Demonstrates integrating WSO2-style LLM rate-limiting policies into LangChain
runnables, chains, and multi-provider fallbacks:
1. Token Bucket evaluation before model invocation (pre-call quota check).
2. Inspection of prompt and completion token constraints.
3. Fallback cascade trigger on RateLimitExceededError (HTTP 429).
4. Standard response metadata injection with token budget status.

Reference:
- WSO2 LLM Rate Limiting Guide: https://wso2.com/api-platform/learn/llm-rate-limiting/
"""

from __future__ import annotations

import math
import time
from typing import Any, Dict, List, Optional
from rich.console import Console

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.runnables import RunnableLambda

console = Console()


class RateLimitExceededError(Exception):
    """Raised when request violates token quotas or TPM ceilings (HTTP 429)."""
    def __init__(self, message: str, retry_after: float = 2.0):
        super().__init__(message)
        self.retry_after = retry_after


class LangChainTokenRateLimiter:
    """Pre-call Token Governor conforming to WSO2 LLM Gateway specifications."""

    def __init__(
        self,
        max_prompt_tokens: int = 2000,
        max_completion_tokens: int = 1000,
        capacity_tokens: float = 5000.0,
        refill_rate_per_sec: float = 1000.0,
    ):
        self.max_prompt_tokens = max_prompt_tokens
        self.max_completion_tokens = max_completion_tokens
        self.capacity_tokens = capacity_tokens
        self.refill_rate_per_sec = refill_rate_per_sec
        self.current_tokens = capacity_tokens
        self.last_refill = time.monotonic()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.current_tokens = min(self.capacity_tokens, self.current_tokens + (elapsed * self.refill_rate_per_sec))
        self.last_refill = now

    def check_and_consume(self, estimated_prompt_tokens: int, estimated_completion_tokens: int = 500) -> Dict[str, Any]:
        self._refill()

        # Enforce Prompt Ceiling
        if estimated_prompt_tokens > self.max_prompt_tokens:
            raise ValueError(
                f"PayloadRejected: Prompt tokens ({estimated_prompt_tokens}) exceed maximum limit ({self.max_prompt_tokens})"
            )

        total_tokens = estimated_prompt_tokens + estimated_completion_tokens
        if total_tokens > self.current_tokens:
            deficit = total_tokens - self.current_tokens
            wait_time = deficit / self.refill_rate_per_sec
            raise RateLimitExceededError(
                f"HTTP 429 Too Many Requests: TPM bucket exhausted. Deficit: {int(deficit)} tokens.",
                retry_after=wait_time,
            )

        self.current_tokens -= total_tokens
        return {
            "consumed": total_tokens,
            "remaining": int(self.current_tokens),
            "limit": int(self.capacity_tokens),
        }


class RateLimitedMockModel(BaseChatModel):
    """Simulates an upstream LLM protected by a WSO2 token governor."""

    model_name: str = "primary-model"
    governor: LangChainTokenRateLimiter = None

    @property
    def _llm_type(self) -> str:
        return "rate_limited_mock"

    def _generate(self, messages: List[BaseMessage], stop=None, run_manager=None, **kwargs) -> ChatResult:
        # Estimate prompt tokens (~4 chars per token)
        total_prompt_text = "".join([m.content for m in messages if isinstance(m.content, str)])
        prompt_tokens = max(1, len(total_prompt_text) // 4)
        
        # Enforce Governor
        token_stats = self.governor.check_and_consume(prompt_tokens)

        content = f"[{self.model_name}] Diagnostic query executed within token budget."
        return ChatResult(
            generations=[
                ChatGeneration(
                    message=AIMessage(
                        content=content,
                        response_metadata={
                            "model": self.model_name,
                            "tokens_remaining": token_stats["remaining"],
                            "rate_limit_policy": "WSO2-Token-Bucket",
                        },
                    )
                )
            ]
        )

    async def _agenerate(self, messages: List[BaseMessage], stop=None, run_manager=None, **kwargs) -> ChatResult:
        return self._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


class BackupMockModel(BaseChatModel):
    """Secondary model for fallback when primary bucket is exhausted."""

    model_name: str = "backup-overflow-model"

    @property
    def _llm_type(self) -> str:
        return "backup_mock"

    def _generate(self, messages: List[BaseMessage], stop=None, run_manager=None, **kwargs) -> ChatResult:
        content = f"[{self.model_name}] Failover successful: Handled request via secondary tier pool."
        return ChatResult(
            generations=[
                ChatGeneration(
                    message=AIMessage(
                        content=content,
                        response_metadata={"model": self.model_name, "failover_reason": "429_RATE_LIMIT"},
                    )
                )
            ]
        )

    async def _agenerate(self, messages: List[BaseMessage], stop=None, run_manager=None, **kwargs) -> ChatResult:
        return self._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


def demonstrate_langchain_rate_limiting():
    """Demonstrates LangChain integration with WSO2 rate limiting and fallback cascade."""
    console.print("\n[bold cyan]=== LangChain Integration: WSO2 Token Rate Limiter & Fallback Cascade ===[/bold cyan]\n")

    # Governor with 1,500 token capacity and 50 tokens/sec refill to demonstrate exhaustion
    governor = LangChainTokenRateLimiter(
        max_prompt_tokens=2000,
        max_completion_tokens=800,
        capacity_tokens=1500.0,
        refill_rate_per_sec=50.0,
    )

    primary = RateLimitedMockModel(model_name="claude-haiku-5-5 (Primary Rate-Limited)", governor=governor)
    backup = BackupMockModel(model_name="gpt-4.1-mini (Secondary Surge Fallback)")

    # Declarative fallback on 429 RateLimitExceededError
    resilient_chain = primary.with_fallbacks([backup])

    requests = [
        "Check BGP peering session status on Router R-01.",
        "Inspect telemetry statistics for optical link Frankfurt-Paris.",
        "Analyze memory buffer saturation on edge leaf switches.",  # Bucket exhausted -> 429 -> Fallback to backup
    ]

    for i, req in enumerate(requests, 1):
        console.print(f"[bold yellow]Request #{i}:[/bold yellow] '{req[:50]}...'")
        try:
            res = resilient_chain.invoke([HumanMessage(content=req)])
            console.print(f"  [green]Result:[/green] {res.content}")
            meta = getattr(res, "response_metadata", {})
            console.print(f"  [magenta]Metadata:[/magenta] {meta}\n")
        except Exception as e:
            console.print(f"  [red]Failed with error: {e}[/red]\n")


if __name__ == "__main__":
    demonstrate_langchain_rate_limiting()
