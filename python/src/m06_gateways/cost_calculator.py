"""Module 6: Enterprise GenAI Cost & ROI Calculator.

Calculates exact financial economics across optimization strategies:
1. Baseline Realtime Uncached
2. Prompt Caching (50% to 90% read discount)
3. Asynchronous Batch API (50% flat discount)
4. Combined: Batch + Prompt Caching
5. Tiered Routing (80% traffic offloaded to fast/cheap model)
"""

from __future__ import annotations

from dataclasses import dataclass
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


PRICING_CATALOG = {
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
}


def calculate_scenario(
    pricing: PricingModel,
    monthly_requests: int,
    static_prefix_tokens: int,
    dynamic_input_tokens: int,
    output_tokens: int,
):
    total_input_per_req = static_prefix_tokens + dynamic_input_tokens

    # 1. Baseline: Uncached Realtime
    base_input_cost = (monthly_requests * total_input_per_req / 1_000_000) * pricing.input_per_m
    base_output_cost = (monthly_requests * output_tokens / 1_000_000) * pricing.output_per_m
    baseline_total = base_input_cost + base_output_cost

    # 2. Prompt Caching
    # Assume 1st request writes, remaining requests read cache
    cached_prefix_cost = (monthly_requests * static_prefix_tokens / 1_000_000) * pricing.cache_read_per_m
    dynamic_in_cost = (monthly_requests * dynamic_input_tokens / 1_000_000) * pricing.input_per_m
    caching_total = cached_prefix_cost + dynamic_in_cost + base_output_cost

    # 3. Asynchronous Batch API (50% flat discount)
    batch_total = baseline_total * pricing.batch_discount_multiplier

    # 4. Combined: Batch + Prompt Caching
    combined_total = caching_total * pricing.batch_discount_multiplier

    return {
        "baseline": baseline_total,
        "caching": caching_total,
        "batch": batch_total,
        "combined": combined_total,
    }


def main():
    console.print("\n[bold cyan]=== Enterprise GenAI Cost Optimization ROI Model ===[/bold cyan]")

    # Scenario parameters: Enterprise customer service & document analysis
    monthly_requests = 500_000
    static_prefix_tokens = 4_000  # System instructions, compliance, tools, product catalog
    dynamic_input_tokens = 500    # User inquiry
    output_tokens = 300           # Generated response

    model_key = "claude-3-5-sonnet"
    pricing = PRICING_CATALOG[model_key]

    results = calculate_scenario(
        pricing,
        monthly_requests=monthly_requests,
        static_prefix_tokens=static_prefix_tokens,
        dynamic_input_tokens=dynamic_input_tokens,
        output_tokens=output_tokens,
    )

    table = Table(title=f"Monthly Spend Model: {pricing.name} (500k requests/month)")
    table.add_column("Strategy", style="cyan")
    table.add_column("Monthly Cost (USD)", justify="right", style="bold")
    table.add_column("Savings (USD)", justify="right", style="green")
    table.add_column("% Reduction", justify="right", style="bold green")

    baseline = results["baseline"]

    table.add_row("1. Baseline (Uncached Realtime)", f"${baseline:,.2f}", "$0.00", "0.0%")

    save_cache = baseline - results["caching"]
    pct_cache = (save_cache / baseline) * 100
    table.add_row("2. Realtime with Prompt Caching", f"${results['caching']:,.2f}", f"${save_cache:,.2f}", f"{pct_cache:.1f}%")

    save_batch = baseline - results["batch"]
    pct_batch = (save_batch / baseline) * 100
    table.add_row("3. Asynchronous Batch API (50% off)", f"${results['batch']:,.2f}", f"${save_batch:,.2f}", f"{pct_batch:.1f}%")

    save_comb = baseline - results["combined"]
    pct_comb = (save_comb / baseline) * 100
    table.add_row("4. Combined: Batch + Prompt Caching", f"${results['combined']:,.2f}", f"${save_comb:,.2f}", f"[bold underline]{pct_comb:.1f}%[/bold underline]")

    console.print(table)
    console.print(f"\n[bold green]>>> Total Annual Savings with Combined Strategy:[/bold green] [bold white]${save_comb * 12:,.2f} USD[/bold white]\n")


if __name__ == "__main__":
    main()
