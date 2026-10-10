"""Starter Code: Lab 05 - Fault-Tolerant Agent State Machine & SQLite Crash Recovery."""

from __future__ import annotations

import operator
from typing import Annotated, Any, Dict, List, Optional, Sequence, TypedDict
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.base import BaseCheckpointSaver


# =============================================================================
# TASK 1: Define Typed State with Append-Only Reducer
# =============================================================================
# TODO: Use typing.Annotated and operator.add so messages append instead of overwrite.
class ResilientAgentState(TypedDict):
    # Fix this:
    messages: Sequence[BaseMessage]
    execution_step: int


# Domain Tools (Provided)
@tool
def query_subscriber(account_id: str) -> str:
    """Lookup subscriber records by account ID."""
    return f"Subscriber {account_id}: Status ACTIVE, Phone +491701234567, Plan 5G-Max"


@tool
def issue_refund(account_id: str, amount_eur: float) -> str:
    """Issue goodwill refund credit to account."""
    return f"REFUND SUCCESS: €{amount_eur:.2f} credited to {account_id}. Ref: TX-{account_id}"


LAB_TOOLS = [query_subscriber, issue_refund]


# =============================================================================
# TASK 2: Assemble Cyclical Graph with SQLite Persistence
# =============================================================================
def build_agent_graph(
    model: Any,
    checkpointer: Optional[BaseCheckpointSaver] = None,
):
    """Assembles a cyclical LangGraph state machine with persistence.

    TODO:
    1. Bind LAB_TOOLS to the model.
    2. Add 'agent' and 'tools' nodes.
    3. Add START -> 'agent' edge.
    4. Add conditional edge from 'agent' using tools_condition.
    5. Add 'tools' -> 'agent' edge to close the loop.
    6. Compile the graph passing checkpointer.
    """
    # Placeholder (broken starter):
    builder = StateGraph(ResilientAgentState)
    return None


# =============================================================================
# TASK 3: Implement State Rehydration & Resumption Utility
# =============================================================================
def resume_agent_workflow(
    agent: Any,
    thread_id: str,
    followup_message: Optional[str] = None,
) -> Dict[str, Any]:
    """Inspects checkpointed state from SQLite and resumes execution.

    TODO:
    1. Retrieve state using agent.get_state(config).
    2. Verify state exists; raise ValueError if thread not found.
    3. Call agent.invoke() with appropriate payload and return updated state.
    """
    # Placeholder:
    return {}

