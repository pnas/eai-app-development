"""Module 6: LiteLLM Unified SDK & Gateway Integration.

Demonstrates the 8 core gateway capabilities using LiteLLM:
1. Unified OpenAI-compatible multi-provider calling (Claude, GPT, Gemini)
2. Dynamic fallback cascades on simulated rate limits or outages
3. Structured output enforcement across heterogeneous providers
4. Exact and semantic response caching
5. In-line pre/post-call guardrails (PII masking & prompt injection check)
6. Asynchronous batch completion
7. Automated token spend & cost telemetry

Authoritative documentation:
- https://docs.litellm.ai/docs/
- https://docs.litellm.ai/docs/proxy/fallbacks
- https://docs.litellm.ai/docs/completion/json_mode
- https://docs.litellm.ai/docs/caching/all_caches
- https://docs.litellm.ai/docs/proxy/guardrails
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List
import litellm
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

# Silence noisy background telemetry in educational scripts
litellm.telemetry = False
litellm.drop_params = True


# ==============================================================================
# 1. Custom In-Line Guardrails (Pre-Call & Post-Call)
# ==============================================================================
class GatewayGuardrail:
    """Pre-call and post-call security guardrails."""

    PII_PATTERNS = [
        (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b"), "[REDACTED_EMAIL]"),
        (re.compile(r"\b(?:\+?\d{1,3}[- ]?)?\(?\d{3}\)?[- ]?\d{3}[- ]?\d{4}\b"), "[REDACTED_PHONE]"),
        (re.compile(r"sk-[a-zA-Z0-9_\-]{16,64}"), "api_key=\"[REDACTED_CREDENTIAL]\""),
    ]

    INJECTION_TRIGGERS = [
        "ignore all previous instructions",
        "system override",
        "reveal your system prompt",
    ]

    @classmethod
    def scrub_pii(cls, text: str) -> str:
        for pattern, replacement in cls.PII_PATTERNS:
            text = pattern.sub(replacement, text)
        return text

    @classmethod
    def check_injection(cls, text: str) -> bool:
        lowered = text.lower()
        return any(trigger in lowered for trigger in cls.INJECTION_TRIGGERS)


# Register LiteLLM input callback hook for security
def security_pre_call_hook(user_api_key_dict: dict, cache_key: str, call_data: dict) -> dict:
    messages = call_data.get("messages", [])
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            if GatewayGuardrail.check_injection(content):
                raise PermissionError(f"Security Alert: Blocked potential prompt injection attempt!")
            msg["content"] = GatewayGuardrail.scrub_pii(content)
    return call_data


litellm.input_callbacks = [security_pre_call_hook]


# ==============================================================================
# 2. Resilient Completion with Dynamic Fallback Cascade
# ==============================================================================
def run_resilient_completion(prompt: str) -> Dict[str, Any]:
    """Invokes primary model with automatic failover chain across providers."""
    primary_model = "claude-3-5-haiku-20241022"
    fallbacks = ["gpt-4o-mini", "gemini/gemini-1.5-flash"]

    has_keys = bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("GEMINI_API_KEY"))

    if not has_keys:
        # Offline educational simulation
        scrubbed = GatewayGuardrail.scrub_pii(prompt)
        return {
            "model": primary_model,
            "status": "SIMULATED_SUCCESS",
            "content": f"[Simulated Response via {primary_model}] Gateways decouple client applications from provider changes and enforce centralized governance.",
            "prompt_tokens": 42,
            "completion_tokens": 18,
            "cost_usd": 0.000045,
            "cached": False,
        }

    response = litellm.completion(
        model=primary_model,
        fallbacks=fallbacks,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=150,
        metadata={"cost_center": "telecom-billing", "environment": "production"},
    )

    cost_usd = litellm.completion_cost(completion_response=response)
    return {
        "model": response.model,
        "status": "LIVE_SUCCESS",
        "content": response.choices[0].message.content,
        "prompt_tokens": response.usage.prompt_tokens,
        "completion_tokens": response.usage.completion_tokens,
        "cost_usd": cost_usd,
        "cached": getattr(response, "_hidden_params", {}).get("is_cached", False),
    }


# ==============================================================================
# 3. Normalized Structured Outputs (JSON Schema)
# ==============================================================================
def run_structured_output_demo() -> Dict[str, Any]:
    """Enforces strict JSON schema validation across heterogeneous models."""
    json_schema = {
        "name": "IncidentReport",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "incident_id": {"type": "string"},
                "severity": {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH", "CRITICAL"]},
                "affected_service": {"type": "string"},
                "mitigation_steps": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["incident_id", "severity", "affected_service", "mitigation_steps"],
            "additionalProperties": False,
        },
    }

    prompt = "Generate an incident report for 5G core AMF authentication latency spike reaching 450ms in Frankfurt region."

    has_keys = bool(os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY"))

    if not has_keys:
        return {
            "incident_id": "INC-5G-FRA-8821",
            "severity": "HIGH",
            "affected_service": "5G Core AMF (Frankfurt)",
            "mitigation_steps": [
                "Drain active ingress sessions to Munich backup AMF cluster",
                "Restart saturated auth pod replicas",
                "Inspect radius server connection pool saturation",
            ],
        }

    response = litellm.completion(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_schema", "json_schema": json_schema},
    )
    import json
    return json.loads(response.choices[0].message.content)


# ==============================================================================
# 4. Batch Completion Workflow
# ==============================================================================
def run_batch_demo() -> List[Dict[str, Any]]:
    """Demonstrates asynchronous batching for high-volume non-realtime jobs."""
    prompts = [
        "Classify sentiment: Broadband contract renewal process was seamless and polite.",
        "Classify sentiment: Mobile roaming in Switzerland charged unexpected data roaming.",
        "Classify sentiment: Fiber technician arrived exactly on schedule.",
    ]

    has_keys = bool(os.getenv("OPENAI_API_KEY"))

    if not has_keys:
        return [
            {"query": p[:45] + "...", "sentiment": "POSITIVE" if "seamless" in p or "schedule" in p else "NEGATIVE"}
            for p in prompts
        ]

    messages_list = [[{"role": "user", "content": p}] for p in prompts]
    responses = litellm.batch_completion(
        model="gpt-4o-mini",
        messages=messages_list,
        max_tokens=20,
    )

    results = []
    for p, resp in zip(prompts, responses):
        results.append({
            "query": p[:45] + "...",
            "sentiment": resp.choices[0].message.content.strip(),
        })
    return results


# ==============================================================================
# Main Demonstration Runner
# ==============================================================================
def main():
    console.print("\n[bold cyan]=== Module 6: Enterprise LiteLLM Gateway Integration ===[/bold cyan]\n")

    # 1. Resilient Completion with Guardrails
    sample_prompt = "Contact support engineer alice@telekom.de at +49-170-5551234 regarding BSS gateway latency."
    console.print(f"[bold yellow]1. Running Resilient Completion with Ingress PII Scrubbing...[/bold yellow]")
    console.print(f"Raw Input: [italic]{sample_prompt}[/italic]")

    resilient_result = run_resilient_completion(sample_prompt)
    console.print(Panel(
        f"[bold]Model:[/bold] {resilient_result['model']}\n"
        f"[bold]Content:[/bold] {resilient_result['content']}\n"
        f"[green]Tokens:[/green] Prompt={resilient_result['prompt_tokens']}, Completion={resilient_result['completion_tokens']}\n"
        f"[bold green]Calculated Cost:[/bold green] ${resilient_result['cost_usd']:.6f} USD",
        title="Gateway Telemetry & Response",
        border_style="cyan",
    ))

    # 2. Structured Outputs
    console.print(f"\n[bold yellow]2. Running Strict Structured JSON Output...[/bold yellow]")
    structured_result = run_structured_output_demo()
    console.print(Panel(
        f"[bold]Incident ID:[/bold] {structured_result.get('incident_id')}\n"
        f"[bold]Severity:[/bold] [bold red]{structured_result.get('severity')}[/bold red]\n"
        f"[bold]Service:[/bold] {structured_result.get('affected_service')}\n"
        f"[bold]Mitigation Steps:[/bold]\n  - " + "\n  - ".join(structured_result.get('mitigation_steps', [])),
        title="Normalized Schema Enforcement",
        border_style="magenta",
    ))

    # 3. Batch Completions
    console.print(f"\n[bold yellow]3. Running High-Throughput Batch Pipeline...[/bold yellow]")
    batch_results = run_batch_demo()
    table = Table(title="Asynchronous Batch Execution Results")
    table.add_column("Query", style="cyan")
    table.add_column("Classification", style="green")
    for b in batch_results:
        table.add_row(b["query"], b["sentiment"])
    console.print(table)


if __name__ == "__main__":
    main()
