"""Module 3 (LangChain): Prompt Caching & KV-Cache Header Injection.

Demonstrates how to utilize provider prompt caching through LangChain:
1. Injecting Anthropic cache breakpoints ({"cache_control": {"type": "ephemeral"}})
   inside content blocks of LangChain SystemMessage.
2. Preserving prompt prefix stability in LCEL chains.
3. Auditing cache_creation_input_tokens vs cache_read_input_tokens.
"""

from __future__ import annotations

import os
from rich.console import Console
from rich.panel import Panel

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_anthropic import ChatAnthropic
from src.langchain_suite.core.env import load_workspace_env

load_workspace_env()

console = Console()

# Large static context to exceed Anthropic Haiku prompt caching threshold (>=2,048 tokens)
TELECOM_SPECIFICATION_PREFIX = """
# TELECOMMUNICATIONS NETWORK STANDARD OPERATING PROCEDURES (TS-9021-V4)
This technical standard defines network fault remediation, optical line diagnostics,
and cell-tower handoff protocols for 5G NextGen Core networks.
SECTION 1: OPTICAL TIME-DOMAIN REFLECTOMETER (OTDR) DIAGNOSTICS
When an optical backhaul reports attenuation exceeding 0.35 dB/km on single-mode fiber (G.652),
the Network Operations Center (NOC) must initiate an automated OTDR trace.
Events with loss greater than 0.5 dB are flagged as severe mechanical splices or macrobends.
SECTION 2: CELL SITE GATEWAY (CSG) PROTOCOLS
All CSG routers running Segment Routing over IPv6 (SRv6) maintain bidirectional forwarding
detection (BFD) timers configured with 10ms intervals and multiplier 3.
Upon 3 consecutive dropped BFD packets, the node shifts traffic to the precomputed
Loop-Free Alternate (TI-LFA) backup path within 50ms.
SECTION 3: ROAMING USER DATA REPLICATION
Subscriber session state in the Unified Data Management (UDM) cluster replicates across
three geo-distributed availability zones using Raft consensus. Latency between AZs
must remain under 8ms round-trip to avoid heartbeat degradation.
""" * 16  # Repeated to surpass Haiku 2048 token cache threshold


def run_caching_demo() -> None:
    """Demonstrates first-turn cache creation vs second-turn cache read."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        console.print("[yellow]Skipping caching demo: ANTHROPIC_API_KEY not set.[/yellow]")
        return

    model_name = os.getenv("ANTHROPIC_MODEL", "claude-haiku-5-5")
    model = ChatAnthropic(
        model=model_name,
        api_key=api_key,
    )


    # In LangChain, prompt caching breakpoints are declared via content block dictionaries
    # with the 'cache_control': {'type': 'ephemeral'} metadata.
    cached_system_message = SystemMessage(
        content=[
            {
                "type": "text",
                "text": TELECOM_SPECIFICATION_PREFIX,
                "cache_control": {"type": "ephemeral"},
            }
        ]
    )

    console.print("\n[bold yellow]=== Module 3: Prompt Caching via LangChain ===[/bold yellow]\n")

    # Turn 1: Cache Miss / Cache Creation
    console.print("[bold cyan]Turn 1: Sending prompt with ephemeral cache breakpoint...[/bold cyan]")
    messages_turn_1 = [
        cached_system_message,
        HumanMessage(content="What is the BFD timer interval for CSG routers in Section 2?"),
    ]
    response_1 = model.invoke(messages_turn_1)

    usage_meta_1 = response_1.usage_metadata or {}
    resp_usage_1 = response_1.response_metadata.get("usage", {})
    cache_creation_1 = resp_usage_1.get("cache_creation_input_tokens", usage_meta_1.get("cache_creation_input_tokens", 0))
    cache_read_1 = resp_usage_1.get("cache_read_input_tokens", usage_meta_1.get("cache_read_input_tokens", 0))
    input_tokens_1 = usage_meta_1.get("input_tokens", resp_usage_1.get("input_tokens", "N/A"))

    console.print(Panel(
        f"Response: {response_1.content}\n\n"
        f"Input Tokens: {input_tokens_1}\n"
        f"Cache Creation Tokens: [green]{cache_creation_1}[/green]\n"
        f"Cache Read Tokens: [blue]{cache_read_1}[/blue]",
        title="Turn 1: Cache Write (Cold)",
    ))

    # Turn 2: Cache Hit / Cache Read (identically prefixed system message)
    console.print("\n[bold cyan]Turn 2: Sending second query reusing identical system prefix...[/bold cyan]")
    messages_turn_2 = [
        cached_system_message,
        HumanMessage(content="What is the maximum permissible round-trip latency between AZs in Section 3?"),
    ]
    response_2 = model.invoke(messages_turn_2)

    usage_meta_2 = response_2.usage_metadata or {}
    resp_usage_2 = response_2.response_metadata.get("usage", {})
    cache_creation_2 = resp_usage_2.get("cache_creation_input_tokens", usage_meta_2.get("cache_creation_input_tokens", 0))
    cache_read_2 = resp_usage_2.get("cache_read_input_tokens", usage_meta_2.get("cache_read_input_tokens", 0))
    input_tokens_2 = usage_meta_2.get("input_tokens", resp_usage_2.get("input_tokens", "N/A"))

    console.print(Panel(
        f"Response: {response_2.content}\n\n"
        f"Input Tokens: {input_tokens_2}\n"
        f"Cache Creation Tokens: [green]{cache_creation_2}[/green]\n"
        f"Cache Read Tokens: [bold blue]{cache_read_2} (90% Cost Reduction!)[/bold blue]",
        title="Turn 2: Cache Hit (Warm)",
    ))


if __name__ == "__main__":
    run_caching_demo()

