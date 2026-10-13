"""Module 6: OpenRouter Integration & Managed Multi-Provider Routing.

Demonstrates:
1. Dynamic model fallback chains via the `models` array & `route: "fallback"`
2. Provider steering (sorting by latency/throughput, zero data retention `data_collection: "deny"`)
3. Structured outputs with strict JSON schema validation
4. Prompt caching inspection (cached input token reporting)
5. OpenRouter Batch API construction for 50% discount inference

Authoritative documentation:
- https://openrouter.ai/docs
- https://openrouter.ai/docs/requests
- https://openrouter.ai/docs/provider-routing
- https://openrouter.ai/docs/structured-outputs
- https://openrouter.ai/docs/prompt-caching
- https://openrouter.ai/docs/batch-quickstart
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from src.m01_paradigms.client_factory import get_openrouter_client

console = Console()


# ==============================================================================
# 1. OpenRouter Request Builder with Fallbacks & Provider Steering
# ==============================================================================
def build_openrouter_payload(
    messages: List[Dict[str, str]],
    primary_model: str = "anthropic/claude-3.5-haiku",
    fallback_models: List[str] = None,
    deny_data_collection: bool = True,
    response_format: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """Constructs a production-ready OpenRouter payload with multi-model fallback and privacy controls."""
    if fallback_models is None:
        fallback_models = ["openai/gpt-4o-mini", "google/gemini-flash-1.5"]

    all_models = [primary_model] + [m for m in fallback_models if m != primary_model]

    extra_body: Dict[str, Any] = {
        "models": all_models,
        "route": "fallback",
        "provider": {
            "order": ["Anthropic", "Google", "OpenAI"],
            "allow_fallbacks": True,
            "data_collection": "deny" if deny_data_collection else "allow",
            "require_parameters": True,
        },
    }

    payload: Dict[str, Any] = {
        "model": primary_model,
        "messages": messages,
        "extra_body": extra_body,
    }

    if response_format:
        payload["response_format"] = response_format

    return payload


# ==============================================================================
# 2. Resilient Completion via OpenRouter
# ==============================================================================
def run_openrouter_routing_demo(prompt: str) -> Dict[str, Any]:
    """Executes a request using OpenRouter with automatic provider and model fallback."""
    if not os.getenv("OPENROUTER_API_KEY"):
        # Educational offline simulation
        return {
            "model": "anthropic/claude-3.5-haiku (simulated)",
            "content": "[Simulated OpenRouter Response] Multi-region failover ensures zero downtime when primary upstream API clusters degrade or exhaust rate limits.",
            "prompt_tokens": 58,
            "completion_tokens": 24,
            "cached_tokens": 40,
            "provider_used": "Anthropic",
            "data_collection": "DENIED",
        }

    client = get_openrouter_client()
    messages = [{"role": "user", "content": prompt}]
    payload = build_openrouter_payload(messages=messages)

    response = client.chat.completions.create(
        model=payload["model"],
        messages=payload["messages"],
        extra_body=payload["extra_body"],
    )

    choice = response.choices[0]
    usage = response.usage
    cached_tokens = getattr(getattr(usage, "prompt_tokens_details", None), "cached_tokens", 0)

    return {
        "model": response.model,
        "content": choice.message.content,
        "prompt_tokens": usage.prompt_tokens,
        "completion_tokens": usage.completion_tokens,
        "cached_tokens": cached_tokens,
        "provider_used": getattr(response, "provider", "Unknown"),
        "data_collection": "DENIED",
    }


# ==============================================================================
# 3. Structured Output on OpenRouter
# ==============================================================================
def run_openrouter_structured_demo() -> Dict[str, Any]:
    """Demonstrates JSON schema enforcement through OpenRouter."""
    schema = {
        "type": "json_schema",
        "json_schema": {
            "name": "TelecomNetworkAlert",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "site_id": {"type": "string"},
                    "alarm_type": {"type": "string", "enum": ["RADIO_LINK_FAILURE", "FIBER_CUT", "POWER_OUTAGE", "TEMPERATURE"]},
                    "impacted_subscribers": {"type": "integer"},
                    "recommended_action": {"type": "string"},
                },
                "required": ["site_id", "alarm_type", "impacted_subscribers", "recommended_action"],
                "additionalProperties": False,
            },
        },
    }

    prompt = "Create a critical alarm for site BERLIN-CENTRAL-09 experiencing a catastrophic fiber cut impacting 8,400 active subscribers."

    if not os.getenv("OPENROUTER_API_KEY"):
        return {
            "site_id": "BERLIN-CENTRAL-09",
            "alarm_type": "FIBER_CUT",
            "impacted_subscribers": 8400,
            "recommended_action": "Reroute DWDM traffic to south ring and dispatch fiber emergency crew.",
        }

    client = get_openrouter_client()
    payload = build_openrouter_payload(
        messages=[{"role": "user", "content": prompt}],
        primary_model="openai/gpt-4o-mini",
        response_format=schema,
    )

    response = client.chat.completions.create(
        model=payload["model"],
        messages=payload["messages"],
        extra_body=payload["extra_body"],
        response_format=payload.get("response_format"),
    )

    return json.loads(response.choices[0].message.content)


# ==============================================================================
# 4. OpenRouter Batch API Payload Blueprint
# ==============================================================================
def generate_batch_request_spec() -> Dict[str, Any]:
    """Generates a sample OpenRouter Batch API payload for 50% discount asynchronous jobs."""
    batch_payload = {
        "endpoint": "/v1/chat/completions",
        "model": "anthropic/claude-3.5-haiku",
        "requests": [
            {
                "custom_id": "req-telecom-doc-001",
                "body": {
                    "messages": [{"role": "user", "content": "Extract customer sentiment from call transcript #101"}],
                    "max_tokens": 100,
                },
            },
            {
                "custom_id": "req-telecom-doc-002",
                "body": {
                    "messages": [{"role": "user", "content": "Extract customer sentiment from call transcript #102"}],
                    "max_tokens": 100,
                },
            },
        ],
        "provider": {
            "data_collection": "deny",
        },
    }
    return batch_payload


# ==============================================================================
# Main Demonstration Runner
# ==============================================================================
def main():
    console.print("\n[bold magenta]=== Module 6: OpenRouter Multi-Provider Auto-Routing & Governance ===[/bold magenta]\n")

    # 1. Routing Demo
    prompt = "Explain why multi-region failover is essential for enterprise LLM gateways."
    console.print(f"[bold yellow]1. Executing Multi-Model Fallback Request (Privacy: Zero Retention)...[/bold yellow]")
    routing_result = run_openrouter_routing_demo(prompt)

    console.print(Panel(
        f"[bold]Selected Model:[/bold] {routing_result['model']}\n"
        f"[bold]Response:[/bold] {routing_result['content']}\n\n"
        f"[green]Tokens:[/green] Input={routing_result['prompt_tokens']}, Cached={routing_result['cached_tokens']}, Output={routing_result['completion_tokens']}\n"
        f"[bold green]Data Policy:[/bold green] {routing_result['data_collection']} (No training on prompts)",
        title="OpenRouter Dynamic Routing Telemetry",
        border_style="magenta",
    ))

    # 2. Structured Outputs Demo
    console.print(f"\n[bold yellow]2. Executing Structured Output Alarm Extraction...[/bold yellow]")
    alarm = run_openrouter_structured_demo()
    console.print(Panel(
        f"[bold]Site ID:[/bold] {alarm['site_id']}\n"
        f"[bold]Alarm Type:[/bold] [bold red]{alarm['alarm_type']}[/bold red]\n"
        f"[bold]Impacted Subscribers:[/bold] {alarm['impacted_subscribers']:,}\n"
        f"[bold]Recommended Action:[/bold] {alarm['recommended_action']}",
        title="Structured Alarm Schema",
        border_style="cyan",
    ))

    # 3. Batch API Specification
    console.print(f"\n[bold yellow]3. OpenRouter Batch API (50% Off Asynchronous Jobs)...[/bold yellow]")
    batch_spec = generate_batch_request_spec()
    console.print(Panel(
        f"[bold]Endpoint:[/bold] POST https://openrouter.ai/api/v1/batches\n"
        f"[bold]Model:[/bold] {batch_spec['model']}\n"
        f"[bold]Batch Items:[/bold] {len(batch_spec['requests'])} tasks\n"
        f"[bold]Discount SLA:[/bold] 24-hour turnaround @ 50% discount on standard token rate\n"
        f"[bold]Privacy:[/bold] provider.data_collection = 'deny'",
        title="Asynchronous Batch API Blueprint",
        border_style="green",
    ))


if __name__ == "__main__":
    main()
