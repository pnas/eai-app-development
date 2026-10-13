"""Module 6: Enterprise GenAI Cost & ROI Calculator.

Calculates exact financial economics across production optimization strategies:
1. Baseline Realtime Uncached
2. Upstream Prompt Caching (50% to 95% read discount)
3. Synchronous Flex Processing (50% flat discount) & Asynchronous Batch API
4. Fast Mode Latency Optimization (1.5x - 2.0x premium for 2.5x speedup)
5. Tiered Routing (80% traffic offloaded to fast/cheap model)
6. Enterprise Gateway Tier: Tiered Routing + Prompt Caching + Gateway Semantic Caching

Official References:
- Latency Optimization: https://developers.openai.com/api/docs/guides/latency-optimization
- Fast Mode: https://developers.openai.com/api/docs/guides/fast-mode
- Prompt Caching: https://developers.openai.com/api/docs/guides/prompt-caching
- Flex Processing: https://developers.openai.com/api/docs/guides/flex-processing
- Batch API: https://developers.openai.com/api/docs/guides/batch
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict
from rich.console import Console
from rich.table import Table

console = Console()


@dataclass
class PricingModel:
    name: str
    input_per_m: float
    output_per_m: float
    cache_read_per_m: float
    batch_discount_multiplier: float = 0.5
    fast_mode_multiplier: float = 1.75
    flex_discount_multiplier: float = 0.5


PRICING_CATALOG: Dict[str, PricingModel] = {
    "gpt-6.1-sol": PricingModel(
        name="OpenAI GPT-6.1 Sol (Flagship Reasoning)",
        input_per_m=2.50,
        output_per_m=10.00,
        cache_read_per_m=0.125,  # 95% discount (0.05x)
    ),
    "gpt-6-astra": PricingModel(
        name="OpenAI GPT-6 Astra (Balanced Reasoning)",
        input_per_m=2.00,
        output_per_m=8.00,
        cache_read_per_m=0.20,  # 90% discount (0.10x)
    ),
    "gpt-6-luna": PricingModel(
        name="OpenAI GPT-6 Luna (Lightweight Reasoning)",
        input_per_m=0.50,
        output_per_m=2.00,
        cache_read_per_m=0.05,  # 90% discount (0.10x)
    ),
    "gpt-4.1": PricingModel(
        name="OpenAI GPT-4.1 (General Instruction)",
        input_per_m=2.00,
        output_per_m=8.00,
        cache_read_per_m=0.20,  # 90% discount (0.10x)
    ),
    "gpt-4.1-mini": PricingModel(
        name="OpenAI GPT-4.1 Mini (High Throughput)",
        input_per_m=0.15,
        output_per_m=0.60,
        cache_read_per_m=0.015,  # 90% discount (0.10x)
    ),
    "claude-sonnet-5-5": PricingModel(
        name="Claude Sonnet 5.5",
        input_per_m=3.00,
        output_per_m=15.00,
        cache_read_per_m=0.15,  # 95% discount
    ),
    "claude-haiku-5-5": PricingModel(
        name="Claude Haiku 5.5",
        input_per_m=0.80,
        output_per_m=4.00,
        cache_read_per_m=0.08,  # 90% discount
    ),
    "claude-3-5-sonnet": PricingModel(
        name="Claude 3.5 Sonnet",
        input_per_m=3.00,
        output_per_m=15.00,
        cache_read_per_m=0.30,  # 90% discount
    ),
    "claude-3-5-haiku": PricingModel(
        name="Claude 3.5 Haiku",
        input_per_m=0.80,
        output_per_m=4.00,
        cache_read_per_m=0.08,  # 90% discount
    ),
    "gpt-4o": PricingModel(
        name="OpenAI GPT-4o",
        input_per_m=2.50,
        output_per_m=10.00,
        cache_read_per_m=1.25,  # 50% discount
    ),
    "gpt-4o-mini": PricingModel(
        name="OpenAI GPT-4o-mini",
        input_per_m=0.15,
        output_per_m=0.60,
        cache_read_per_m=0.075,  # 50% discount
    ),
    "gemini-2.0-flash": PricingModel(
        name="Google Gemini 2.0 Flash",
        input_per_m=0.10,
        output_per_m=0.40,
        cache_read_per_m=0.025,  # 75% discount
    ),
}


def calculate_scenario(
    primary: PricingModel,
    economy: PricingModel,
    monthly_requests: int,
    static_prefix_tokens: int,
    dynamic_input_tokens: int,
    output_tokens: int,
    semantic_cache_hit_rate: float = 0.25,
    economy_offload_ratio: float = 0.80,
) -> Dict[str, float]:
    total_input_per_req = static_prefix_tokens + dynamic_input_tokens

    # 1. Baseline: Uncached Realtime on Primary Model
    base_input_cost = (monthly_requests * total_input_per_req / 1_000_000) * primary.input_per_m
    base_output_cost = (monthly_requests * output_tokens / 1_000_000) * primary.output_per_m
    baseline_total = base_input_cost + base_output_cost

    # 2. Upstream Prompt Caching
    cached_prefix_cost = (monthly_requests * static_prefix_tokens / 1_000_000) * primary.cache_read_per_m
    dynamic_in_cost = (monthly_requests * dynamic_input_tokens / 1_000_000) * primary.input_per_m
    caching_total = cached_prefix_cost + dynamic_in_cost + base_output_cost

    # 3. Asynchronous Batch API (50% flat discount)
    batch_total = baseline_total * primary.batch_discount_multiplier

    # 4. Combined: Batch + Prompt Caching
    combined_total = caching_total * primary.batch_discount_multiplier

    # 5. Tiered Routing (80% offloaded to economy model, 20% to primary)
    primary_reqs = monthly_requests * (1.0 - economy_offload_ratio)
    economy_reqs = monthly_requests * economy_offload_ratio

    primary_cost = (primary_reqs * total_input_per_req / 1_000_000) * primary.input_per_m + (primary_reqs * output_tokens / 1_000_000) * primary.output_per_m
    economy_cost = (economy_reqs * total_input_per_req / 1_000_000) * economy.input_per_m + (economy_reqs * output_tokens / 1_000_000) * economy.output_per_m
    tiered_total = primary_cost + economy_cost

    # 6. Full Enterprise Gateway: Semantic Caching (25% hit @ $0) + Tiered Routing + Prompt Caching
    effective_reqs = monthly_requests * (1.0 - semantic_cache_hit_rate)
    eff_primary_reqs = effective_reqs * (1.0 - economy_offload_ratio)
    eff_economy_reqs = effective_reqs * economy_offload_ratio

    # Primary with prompt caching
    gw_primary = (
        (eff_primary_reqs * static_prefix_tokens / 1_000_000) * primary.cache_read_per_m
        + (eff_primary_reqs * dynamic_input_tokens / 1_000_000) * primary.input_per_m
        + (eff_primary_reqs * output_tokens / 1_000_000) * primary.output_per_m
    )
    # Economy with prompt caching
    gw_economy = (
        (eff_economy_reqs * static_prefix_tokens / 1_000_000) * economy.cache_read_per_m
        + (eff_economy_reqs * dynamic_input_tokens / 1_000_000) * economy.input_per_m
        + (eff_economy_reqs * output_tokens / 1_000_000) * economy.output_per_m
    )
    gateway_total = gw_primary + gw_economy

    return {
        "baseline": baseline_total,
        "caching": caching_total,
        "batch": batch_total,
        "combined": combined_total,
        "tiered": tiered_total,
        "gateway_full": gateway_total,
    }


def main():
    console.print("\n[bold cyan]=== Enterprise GenAI Cost Optimization ROI Model ===[/bold cyan]\n")

    # Scenario parameters: Enterprise customer service & document analysis
    monthly_requests = 1_000_000
    static_prefix_tokens = 4_000  # System instructions, compliance, tools, product catalog
    dynamic_input_tokens = 500    # User inquiry
    output_tokens = 300           # Generated response

    primary = PRICING_CATALOG["claude-3-5-sonnet"]
    economy = PRICING_CATALOG["gpt-4o-mini"]

    results = calculate_scenario(
        primary=primary,
        economy=economy,
        monthly_requests=monthly_requests,
        static_prefix_tokens=static_prefix_tokens,
        dynamic_input_tokens=dynamic_input_tokens,
        output_tokens=output_tokens,
        semantic_cache_hit_rate=0.25,
        economy_offload_ratio=0.80,
    )

    table = Table(title=f"Monthly Spend Model: {primary.name} + {economy.name} (1,000,000 reqs/mo)")
    table.add_column("Strategy Tier", style="cyan")
    table.add_column("Monthly Spend", justify="right", style="bold")
    table.add_column("Monthly Savings", justify="right", style="green")
    table.add_column("% Reduction", justify="right", style="bold green")

    baseline = results["baseline"]
    table.add_row("1. Baseline (Uncached Realtime)", f"${baseline:,.2f}", "$0.00", "0.0%")

    save_cache = baseline - results["caching"]
    table.add_row("2. Realtime with Prompt Caching (90% off prefix)", f"${results['caching']:,.2f}", f"${save_cache:,.2f}", f"{(save_cache / baseline) * 100:.1f}%")

    save_batch = baseline - results["batch"]
    table.add_row("3. Asynchronous Batch API (50% flat off)", f"${results['batch']:,.2f}", f"${save_batch:,.2f}", f"{(save_batch / baseline) * 100:.1f}%")

    save_comb = baseline - results["combined"]
    table.add_row("4. Combined: Batch + Prompt Caching", f"${results['combined']:,.2f}", f"${save_comb:,.2f}", f"{(save_comb / baseline) * 100:.1f}%")

    save_tier = baseline - results["tiered"]
    table.add_row("5. Tiered Routing (80% to Mini, 20% to Sonnet)", f"${results['tiered']:,.2f}", f"${save_tier:,.2f}", f"{(save_tier / baseline) * 100:.1f}%")

    save_gw = baseline - results["gateway_full"]
    pct_gw = (save_gw / baseline) * 100
    table.add_row(
        "6. Enterprise Gateway (Tiering + Caches)",
        f"${results['gateway_full']:,.2f}",
        f"${save_gw:,.2f}",
        f"[bold underline]{pct_gw:.1f}%[/bold underline]",
    )

    console.print(table)
    console.print(f"\n[bold green]>>> Annual Savings with Full Enterprise Gateway Architecture:[/bold green] [bold white]${save_gw * 12:,.2f} USD[/bold white]\n")


if __name__ == "__main__":
    main()
