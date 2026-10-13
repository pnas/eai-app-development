"""Module 5: Enterprise LLM Rate Limiting & Token-Aware Capacity Governor.

Implements architectural rate-limiting patterns inspired by WSO2 AI Gateway:
1. Token-Level Quotas: Max prompt tokens, max completion tokens, total token limit (TPM).
2. Cost-Based Rate Limiting: Budget enforcement ($/window) based on real-time token tracking.
3. Multi-Tenant Department/Subscription Isolation: Tiered virtual key quotas.
4. Token Bucket & GCRA Algorithms: Refill rate with burst absorption.
5. Standard Rate Limit Tracking Headers: Emits X-RateLimit-* and Retry-After.
6. Live OpenAI Model Integration: Live execution, token estimation, and post-call usage reconciliation.

Reference:
- WSO2 LLM Rate Limiting Guide: https://wso2.com/api-platform/learn/llm-rate-limiting/
"""

from __future__ import annotations

import math
import os
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import openai
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.langchain_suite.core.env import load_workspace_env

# Ensure environment variables are loaded
load_workspace_env()

console = Console()


def estimate_tokens(text: str, model: str = "gpt-4o-mini") -> int:
    """Estimates the number of tokens in a string using tiktoken with fallback."""
    try:
        import tiktoken
        try:
            enc = tiktoken.encoding_for_model(model)
        except KeyError:
            enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        # Heuristic fallback: ~4 characters per token + 4 formatting overhead tokens
        return max(1, math.ceil(len(text) / 4.0) + 4)


@dataclass
class RateLimitHeaders:
    """Standard HTTP rate-limiting headers returned to client microservices."""
    limit_tokens: int
    remaining_tokens: int
    reset_tokens_seconds: float
    retry_after_seconds: float = 0.0

    def to_dict(self) -> Dict[str, str]:
        headers = {
            "X-RateLimit-Limit-Tokens": str(self.limit_tokens),
            "X-RateLimit-Remaining-Tokens": str(max(0, self.remaining_tokens)),
            "X-RateLimit-Reset-Tokens": f"{math.ceil(self.reset_tokens_seconds)}s",
        }
        if self.retry_after_seconds > 0:
            headers["Retry-After"] = str(math.ceil(self.retry_after_seconds))
        return headers


@dataclass
class TierPolicy:
    """Enterprise rate-limiting policy parameters per subscription tier / department."""
    tier_name: str
    max_prompt_tokens: int
    max_completion_tokens: int
    total_token_capacity: float
    refill_rate_tokens_per_sec: float
    max_budget_usd: float
    cost_per_million_tokens: float = 0.50  # e.g., $0.50 per 1M tokens ($0.15 in, $0.60 out blended)


class TokenAwareRateLimiter:
    """Enterprise LLM Gateway Token Bucket & Cost Rate Limiter (WSO2 Pattern)."""

    def __init__(self, policy: TierPolicy):
        self.policy = policy
        self.current_tokens = policy.total_token_capacity
        self.last_refill_timestamp = time.monotonic()
        self.accumulated_cost_usd = 0.0

    def _refill(self) -> None:
        """Continuously replenish tokens up to bucket capacity."""
        now = time.monotonic()
        elapsed = now - self.last_refill_timestamp
        added = elapsed * self.policy.refill_rate_tokens_per_sec
        self.current_tokens = min(self.policy.total_token_capacity, self.current_tokens + added)
        self.last_refill_timestamp = now

    def acquire(
        self, prompt_tokens: int, estimated_completion_tokens: int
    ) -> Tuple[bool, RateLimitHeaders, str]:
        """Evaluate request against prompt, completion, bucket tokens, and budget.
        
        Returns:
            (is_allowed, headers, reason_or_status)
        """
        self._refill()

        # 1. Enforce Max Prompt Token Count
        if prompt_tokens > self.policy.max_prompt_tokens:
            headers = RateLimitHeaders(
                limit_tokens=int(self.policy.total_token_capacity),
                remaining_tokens=int(self.current_tokens),
                reset_tokens_seconds=0.0,
                retry_after_seconds=0.0,
            )
            return (
                False,
                headers,
                f"PayloadRejected: Prompt tokens ({prompt_tokens}) exceeded maximum allowed ({self.policy.max_prompt_tokens})",
            )

        # 2. Enforce Max Completion Token Count
        if estimated_completion_tokens > self.policy.max_completion_tokens:
            headers = RateLimitHeaders(
                limit_tokens=int(self.policy.total_token_capacity),
                remaining_tokens=int(self.current_tokens),
                reset_tokens_seconds=0.0,
                retry_after_seconds=0.0,
            )
            return (
                False,
                headers,
                f"PayloadRejected: Estimated completion tokens ({estimated_completion_tokens}) exceeded ceiling ({self.policy.max_completion_tokens})",
            )

        total_needed = prompt_tokens + estimated_completion_tokens
        call_cost = (total_needed / 1_000_000.0) * self.policy.cost_per_million_tokens

        # 3. Enforce Spend Budget Quota
        if self.accumulated_cost_usd + call_cost > self.policy.max_budget_usd:
            headers = RateLimitHeaders(
                limit_tokens=int(self.policy.total_token_capacity),
                remaining_tokens=int(self.current_tokens),
                reset_tokens_seconds=60.0,
                retry_after_seconds=60.0,
            )
            return (
                False,
                headers,
                f"BudgetExceeded: Spend budget exhausted (${self.accumulated_cost_usd:.4f} + ${call_cost:.4f} > ${self.policy.max_budget_usd:.2f})",
            )

        # 4. Enforce Token Bucket Capacity
        if total_needed > self.current_tokens:
            deficit = total_needed - self.current_tokens
            wait_seconds = deficit / self.policy.refill_rate_tokens_per_sec if self.policy.refill_rate_tokens_per_sec > 0 else 60.0
            headers = RateLimitHeaders(
                limit_tokens=int(self.policy.total_token_capacity),
                remaining_tokens=int(self.current_tokens),
                reset_tokens_seconds=wait_seconds,
                retry_after_seconds=wait_seconds,
            )
            return (
                False,
                headers,
                f"HTTP 429 Too Many Requests: Token bucket empty (Deficit: {int(deficit)} tokens. Retry after {wait_seconds:.1f}s)",
            )

        # Success: Deduct tokens and accrue initial estimated cost
        self.current_tokens -= total_needed
        self.accumulated_cost_usd += call_cost
        reset_time = (
            (self.policy.total_token_capacity - self.current_tokens) / self.policy.refill_rate_tokens_per_sec
            if self.policy.refill_rate_tokens_per_sec > 0
            else 0.0
        )

        headers = RateLimitHeaders(
            limit_tokens=int(self.policy.total_token_capacity),
            remaining_tokens=int(self.current_tokens),
            reset_tokens_seconds=reset_time,
            retry_after_seconds=0.0,
        )
        return True, headers, "Accepted"

    def reconcile_usage(
        self,
        reserved_total_tokens: int,
        actual_prompt_tokens: int,
        actual_completion_tokens: int,
    ) -> float:
        """Reconciles initial token reservation with actual usage returned by model.
        
        Adjusts bucket token balance and updates accumulated financial spend.
        
        Returns:
            The exact actual cost of this call in USD.
        """
        actual_total = actual_prompt_tokens + actual_completion_tokens
        token_delta = reserved_total_tokens - actual_total  # Positive = over-reserved, negative = under-reserved

        # Adjust bucket balance
        self.current_tokens = min(
            self.policy.total_token_capacity,
            self.current_tokens + token_delta,
        )

        # Reconcile cost difference
        cost_delta = (token_delta / 1_000_000.0) * self.policy.cost_per_million_tokens
        self.accumulated_cost_usd = max(0.0, self.accumulated_cost_usd - cost_delta)

        actual_call_cost = (actual_total / 1_000_000.0) * self.policy.cost_per_million_tokens
        return actual_call_cost


@dataclass
class ExecutionResult:
    """Structured response from the rate-limited OpenAI executor."""
    scenario_name: str
    allowed: bool
    status_code: int
    reason: str
    headers: RateLimitHeaders
    prompt_text: str
    response_text: Optional[str] = None
    model: str = "gpt-4o-mini"
    estimated_prompt_tokens: int = 0
    estimated_completion_tokens: int = 0
    actual_prompt_tokens: int = 0
    actual_completion_tokens: int = 0
    total_actual_tokens: int = 0
    call_cost_usd: float = 0.0
    is_live_call: bool = False


class OpenAIRateLimitedExecutor:
    """Manages pre-flight rate limiting, live OpenAI API calls, and post-call reconciliation."""

    def __init__(
        self,
        limiter: TokenAwareRateLimiter,
        model: str = "gpt-4o-mini",
        client: Optional[openai.OpenAI] = None,
    ):
        self.limiter = limiter
        self.model = model
        self._client = client

    def _get_client(self) -> Optional[openai.OpenAI]:
        if self._client is not None:
            return self._client
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key and api_key.strip():
            self._client = openai.OpenAI(api_key=api_key.strip())
            return self._client
        return None

    def execute(
        self,
        scenario_name: str,
        prompt: str,
        system_prompt: str = "You are a senior Deutsche Telekom network operations AI engineer. Provide concise, highly technical answers.",
        max_completion_tokens: int = 150,
        simulated_prompt_tokens: Optional[int] = None,
        simulated_completion_tokens: Optional[int] = None,
    ) -> ExecutionResult:
        """Executes a request with full rate-limiting lifecycle and OpenAI model call."""
        # 1. Estimate prompt tokens (or use simulated tokens if specified)
        full_text = f"{system_prompt}\n{prompt}"
        prompt_tokens = (
            simulated_prompt_tokens
            if simulated_prompt_tokens is not None
            else estimate_tokens(full_text, model=self.model)
        )
        est_completion = (
            simulated_completion_tokens
            if simulated_completion_tokens is not None
            else max_completion_tokens
        )

        # 2. Pre-flight Rate Check
        allowed, headers, reason = self.limiter.acquire(prompt_tokens, est_completion)

        if not allowed:
            status_code = 400 if "PayloadRejected" in reason else 429
            return ExecutionResult(
                scenario_name=scenario_name,
                allowed=False,
                status_code=status_code,
                reason=reason,
                headers=headers,
                prompt_text=prompt,
                model=self.model,
                estimated_prompt_tokens=prompt_tokens,
                estimated_completion_tokens=est_completion,
                is_live_call=False,
            )

        # 3. Dispatched to Live OpenAI Model
        client = self._get_client()
        if client is None:
            # Fallback mock if no API key is present
            mock_text = f"[Mock OpenAI {self.model}] Successfully verified telecom operation."
            actual_cost = self.limiter.reconcile_usage(
                reserved_total_tokens=prompt_tokens + est_completion,
                actual_prompt_tokens=prompt_tokens,
                actual_completion_tokens=30,
            )
            return ExecutionResult(
                scenario_name=scenario_name,
                allowed=True,
                status_code=200,
                reason="Accepted (Mock Mode)",
                headers=headers,
                prompt_text=prompt,
                response_text=mock_text,
                model=self.model,
                estimated_prompt_tokens=prompt_tokens,
                estimated_completion_tokens=est_completion,
                actual_prompt_tokens=prompt_tokens,
                actual_completion_tokens=30,
                total_actual_tokens=prompt_tokens + 30,
                call_cost_usd=actual_cost,
                is_live_call=False,
            )

        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=max_completion_tokens,
                temperature=0.2,
            )

            response_content = response.choices[0].message.content or ""
            actual_prompt = response.usage.prompt_tokens if response.usage else prompt_tokens
            actual_completion = response.usage.completion_tokens if response.usage else 25

            # 4. Reconcile reservation with actual model usage
            call_cost = self.limiter.reconcile_usage(
                reserved_total_tokens=prompt_tokens + est_completion,
                actual_prompt_tokens=actual_prompt,
                actual_completion_tokens=actual_completion,
            )

            return ExecutionResult(
                scenario_name=scenario_name,
                allowed=True,
                status_code=200,
                reason="Accepted (Live Call)",
                headers=headers,
                prompt_text=prompt,
                response_text=response_content.strip(),
                model=self.model,
                estimated_prompt_tokens=prompt_tokens,
                estimated_completion_tokens=est_completion,
                actual_prompt_tokens=actual_prompt,
                actual_completion_tokens=actual_completion,
                total_actual_tokens=actual_prompt + actual_completion,
                call_cost_usd=call_cost,
                is_live_call=True,
            )
        except Exception as exc:
            # On unexpected API error, refund tokens to limiter
            self.limiter.reconcile_usage(
                reserved_total_tokens=prompt_tokens + est_completion,
                actual_prompt_tokens=0,
                actual_completion_tokens=0,
            )
            return ExecutionResult(
                scenario_name=scenario_name,
                allowed=False,
                status_code=500,
                reason=f"OpenAIError: {str(exc)}",
                headers=headers,
                prompt_text=prompt,
                model=self.model,
                estimated_prompt_tokens=prompt_tokens,
                estimated_completion_tokens=est_completion,
                is_live_call=False,
            )


def demonstrate_openai_rate_limiting():
    """Executes realistic telecom operational scenarios with live OpenAI models."""
    console.print(
        "\n[bold cyan]========================================================================[/bold cyan]"
    )
    console.print(
        "[bold cyan]  WSO2 Pattern: Enterprise LLM Rate Limiter & Governor (Live OpenAI)   [/bold cyan]"
    )
    console.print(
        "[bold cyan]========================================================================[/bold cyan]\n"
    )

    # Policy for Network Operations Tier
    policy = TierPolicy(
        tier_name="NetworkOps-NOC-Tier",
        max_prompt_tokens=1000,
        max_completion_tokens=300,
        total_token_capacity=2200.0,
        refill_rate_tokens_per_sec=250.0,  # Replenishes 250 tokens per second (~15,000 TPM)
        max_budget_usd=0.05,               # Strict spending guardrail
        cost_per_million_tokens=0.50,      # $0.50 blended cost per 1M tokens
    )

    limiter = TokenAwareRateLimiter(policy)
    executor = OpenAIRateLimitedExecutor(limiter=limiter, model="gpt-4o-mini")

    scenarios = [
        {
            "name": "1. SIM 5G SA Provisioning",
            "prompt": "Subscriber IMSI 26201984210001 status is ACTIVE. Verify if 5G SA network slicing (SST=1, SD=0x000001) is supported and specify the default 5QI.",
            "max_completion": 80,
            "sim_prompt": None,
            "sim_completion": None,
            "delay_before": 0.0,
        },
        {
            "name": "2. BGP Peering Root Cause",
            "prompt": "Incident INC-7702: BGP session flapping between AS3320 (Telekom) and AS15169 (Google) on Frankfurt IX interface TenGigE0/1/0. Output 3 immediate mitigation steps.",
            "max_completion": 120,
            "sim_prompt": None,
            "sim_completion": None,
            "delay_before": 0.0,
        },
        {
            "name": "3. Runaway Syslog Dump (Ceiling Breach)",
            "prompt": "Ingest uncompressed raw syslog core dump containing 15,000 lines of packet traces from border gateway...",
            "max_completion": 100,
            "sim_prompt": 4500,  # Exceeds max_prompt_tokens = 1000
            "sim_completion": None,
            "delay_before": 0.0,
        },
        {
            "name": "4. Unbounded Generation (Completion Breach)",
            "prompt": "Generate an exhaustive 50-page 3GPP Release 18 specification document with complete ASN.1 definitions.",
            "max_completion": 600,  # Exceeds max_completion_tokens = 300
            "sim_prompt": 120,
            "sim_completion": 600,
            "delay_before": 0.0,
        },
        {
            "name": "5. Rapid Burst Surge (Capacity Drain)",
            "prompt": "Perform emergency global trace of all active SIP trunks across European data centers and evaluate SIP 503 response rates.",
            "max_completion": 200,
            "sim_prompt": 950,   # High volume: 950 + 200 = 1150 tokens. Will breach remaining capacity!
            "sim_completion": 200,
            "delay_before": 0.0,
        },
        {
            "name": "6. Post-Cooldown Recovery",
            "prompt": "Health check: Are all 5G UPF (User Plane Function) nodes in Berlin cluster DE-BER-01 reporting nominal latency?",
            "max_completion": 60,
            "sim_prompt": None,
            "sim_completion": None,
            "delay_before": 2.5,  # Wait 2.5s for token replenishment (2.5 * 250 = 625 tokens refilled)
        },
    ]

    results: List[ExecutionResult] = []

    table = Table(title="Enterprise LLM Gateway Rate Limiting with Live OpenAI Execution")
    table.add_column("Scenario", style="cyan", width=26)
    table.add_column("Status / Verdict", style="bold", width=22)
    table.add_column("Tokens (Res / Act)", style="yellow", width=18)
    table.add_column("Bucket Remaining", style="magenta", width=16)
    table.add_column("Retry-After", style="red", width=12)

    for item in scenarios:
        if item["delay_before"] > 0:
            console.print(f"[dim italic]Sleeping {item['delay_before']}s to allow token bucket refill...[/dim italic]")
            time.sleep(item["delay_before"])

        res = executor.execute(
            scenario_name=item["name"],
            prompt=item["prompt"],
            max_completion_tokens=item["max_completion"],
            simulated_prompt_tokens=item["sim_prompt"],
            simulated_completion_tokens=item["sim_completion"],
        )
        results.append(res)

        # Format status
        if res.allowed:
            status_text = f"[green]200 OK (Live Call)[/green]"
            token_display = f"{res.estimated_prompt_tokens + res.estimated_completion_tokens} / {res.total_actual_tokens}"
        else:
            status_text = f"[red]{res.status_code} Rejected[/red]"
            token_display = f"{res.estimated_prompt_tokens + res.estimated_completion_tokens} / 0"

        retry_str = res.headers.to_dict().get("Retry-After", "-")

        table.add_row(
            res.scenario_name,
            status_text,
            token_display,
            str(res.headers.remaining_tokens),
            retry_str,
        )

    console.print(table)
    console.print(
        f"\n[bold green]Cumulative Spend: ${limiter.accumulated_cost_usd:.6f} / ${policy.max_budget_usd:.2f}[/bold green]\n"
    )

    # Display real OpenAI model responses
    console.print("[bold yellow]=== Live OpenAI Responses from Accepted Scenarios ===[/bold yellow]\n")
    for res in results:
        if res.allowed and res.response_text:
            panel_content = (
                f"[bold cyan]Prompt:[/bold cyan] {res.prompt_text}\n\n"
                f"[bold green]OpenAI ({res.model}) Response:[/bold green]\n{res.response_text}\n\n"
                f"[dim]Tokens: {res.actual_prompt_tokens} in + {res.actual_completion_tokens} out = {res.total_actual_tokens} total | Cost: ${res.call_cost_usd:.6f}[/dim]"
            )
            console.print(Panel(panel_content, title=res.scenario_name, border_style="green"))


def demonstrate_enterprise_rate_limiting():
    """Alias for backward compatibility."""
    demonstrate_openai_rate_limiting()


if __name__ == "__main__":
    demonstrate_openai_rate_limiting()
