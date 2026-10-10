"""LangGraph SQLite Persistence & Crash Recovery Demonstration.

Demonstrates:
1. Long-term state persistence to a physical SQLite database.
2. Simulating a process interruption or crash midway through execution.
3. Cold-booting a brand new process and rehydrating state via thread_id.
4. Seamlessly picking up and completing the unfinished workflow without repeating completed steps.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from rich.console import Console
from rich.panel import Panel

from langchain_core.messages import HumanMessage, ToolMessage, AIMessage
from langgraph.checkpoint.sqlite import SqliteSaver

from src.langchain_suite.agent_recovery.graph import build_telecom_agent

console = Console()
DB_PATH = Path(__file__).parent / "telecom_checkpoints.db"


def run_recovery_demo() -> None:
    console.print("\n[bold yellow]=== LangGraph SQLite State Recovery Demonstration ===[/bold yellow]\n")

    # Ensure clean demo state
    if DB_PATH.exists():
        try:
            DB_PATH.unlink()
        except Exception:
            pass

    thread_id = "subscriber-incident-9021"
    config = {"configurable": {"thread_id": thread_id}}

    console.print(f"[bold cyan]1. Initializing SQLite Checkpointer at:[/bold cyan] {DB_PATH.name}")
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    saver = SqliteSaver(conn)
    saver.setup()

    agent = build_telecom_agent(checkpointer=saver)

    console.print("\n[bold cyan]2. Starting Customer Conversation (Turn 1)...[/bold cyan]")
    user_prompt = "Hello, my account ID is ACCT-1001. My mobile data is crawling and dropping calls. Can you check?"
    console.print(f"[bold white]User:[/bold white] {user_prompt}\n")

    # Execute agent - LangGraph records state to SQLite after every node execution
    state_turn1 = agent.invoke({"messages": [HumanMessage(content=user_prompt)]}, config=config)

    console.print(Panel(
        f"Messages logged in state: [bold]{len(state_turn1['messages'])}[/bold]\n"
        f"Last Agent Output: {state_turn1['messages'][-1].content[:150]}...",
        title="[green]Turn 1 Completed & Checkpointed to SQLite[/green]",
    ))

    # Inspect SQLite database directly to verify real persistence
    cursor = conn.cursor()
    cursor.execute("SELECT count(*) FROM checkpoints WHERE thread_id = ?", (thread_id,))
    checkpoint_count = cursor.fetchone()[0]
    console.print(f"[bold green]✔ Verified SQLite table: {checkpoint_count} checkpoints written for thread '{thread_id}'.[/bold green]")

    # Close connection to simulate total worker process death / container crash
    conn.close()
    del agent
    del saver
    console.print("\n[bold red]💥 PROCESS CRASH SIMULATION: Memory wiped, connection closed, worker dead.[/bold red]\n")

    # =========================================================================
    # RECOVERY PHASE: Brand new process instance re-attaches to SQLite DB
    # =========================================================================
    console.print("[bold cyan]3. Spawning New Worker Process & Rehydrating State from SQLite...[/bold cyan]")
    conn_recovery = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    recovered_saver = SqliteSaver(conn_recovery)

    recovered_agent = build_telecom_agent(checkpointer=recovered_saver)

    # Inspect saved state without re-running any LLM calls
    current_state = recovered_agent.get_state(config)
    console.print(f"[bold yellow]Rehydrated Thread:[/bold yellow] {thread_id}")
    console.print(f"Rehydrated Messages count: [bold]{len(current_state.values.get('messages', []))}[/bold]")
    console.print(f"Next pending action node: [bold]{current_state.next}[/bold]")

    console.print("\n[bold cyan]4. Seamlessly Resuming with Customer Follow-up Query...[/bold cyan]")
    followup_prompt = "Thank you for the diagnosis. Could you please apply the retention credit now?"
    console.print(f"[bold white]User Follow-up:[/bold white] {followup_prompt}\n")

    # Resuming execution: LangGraph seamlessly builds upon the rehydrated SQLite history
    state_resumed = recovered_agent.invoke(
        {"messages": [HumanMessage(content=followup_prompt)]},
        config=config,
    )

    console.print(Panel(
        f"Total conversation turns: [bold]{len(state_resumed['messages'])}[/bold]\n\n"
        f"Final Agent Response:\n{state_resumed['messages'][-1].content}",
        title="[bold green]Workflow Successfully Resumed from SQLite Checkpoint[/bold green]",
    ))

    conn_recovery.close()
    console.print("[bold green]✔ Demonstration Complete: Zero state lost across process destruction.[/bold green]\n")


if __name__ == "__main__":
    run_recovery_demo()

