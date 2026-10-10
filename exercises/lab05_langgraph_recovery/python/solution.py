"""Reference Solution: Lab 05 - Fault-Tolerant Agent State Machine & SQLite Crash Recovery."""

from __future__ import annotations

import operator
from typing import Annotated, Any, Dict, List, Optional, Sequence, TypedDict
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.sqlite import SqliteSaver


# 1. Define Typed State with Append-Only Reducer
class ResilientAgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    execution_step: int


# 2. Domain Tools
@tool
def query_subscriber(account_id: str) -> str:
    """Lookup subscriber records by account ID."""
    return f"Subscriber {account_id}: Status ACTIVE, Phone +491701234567, Plan 5G-Max"


@tool
def issue_refund(account_id: str, amount_eur: float) -> str:
    """Issue goodwill refund credit to account."""
    return f"REFUND SUCCESS: €{amount_eur:.2f} credited to {account_id}. Ref: TX-{account_id}"


LAB_TOOLS = [query_subscriber, issue_refund]


# 3. Graph Assembly Function
def build_agent_graph(
    model: Any,
    checkpointer: Optional[BaseCheckpointSaver] = None,
):
    """Assembles a cyclical LangGraph state machine with persistence."""
    bound_model = model.bind_tools(LAB_TOOLS) if hasattr(model, "bind_tools") else model

    def agent_node(state: ResilientAgentState) -> Dict[str, Any]:
        response = bound_model.invoke(state["messages"])
        step = state.get("execution_step", 0) + 1
        return {"messages": [response], "execution_step": step}

    builder = StateGraph(ResilientAgentState)

    builder.add_node("agent", agent_node)
    builder.add_node("tools", ToolNode(LAB_TOOLS))

    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", tools_condition)
    builder.add_edge("tools", "agent")

    return builder.compile(checkpointer=checkpointer)


# 4. State Rehydration & Resumption Utility
def resume_agent_workflow(
    agent: Any,
    thread_id: str,
    followup_message: Optional[str] = None,
) -> Dict[str, Any]:
    """Inspects checkpointed state from SQLite and resumes execution."""
    config = {"configurable": {"thread_id": thread_id}}

    state = agent.get_state(config)
    if not state or not state.values:
        raise ValueError(f"No checkpoint found for thread_id: '{thread_id}'")

    if followup_message:
        input_payload = {"messages": [HumanMessage(content=followup_message)]}
    else:
        # Resume pending interrupted state without adding a new human message
        input_payload = None

    return agent.invoke(input_payload, config=config)

