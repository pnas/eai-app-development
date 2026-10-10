"""Stateful Telecom Support Agent with LangGraph & SQLite Persistence."""

from __future__ import annotations

import operator
from typing import Annotated, Sequence, TypedDict, Optional
from langchain_core.messages import BaseMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.base import BaseCheckpointSaver

from src.langchain_suite.core.models import get_chat_model
from src.langchain_suite.agent_recovery.tools import (
    lookup_telecom_account,
    diagnose_network_cell,
    apply_retention_credit,
)

SYSTEM_AGENT_PROMPT = """
You are an autonomous Tier-2 Technical Support Agent for a mobile telecom provider.
You have access to 3 tools:
1. lookup_telecom_account: Look up subscriber name, plan, phone number, and balance.
2. diagnose_network_cell: Check RF tower health and packet loss for a phone number.
3. apply_retention_credit: Apply up to €50 goodwill balance credit if an active outage degraded service.

Always check the account first to find the subscriber's phone number, run diagnostics,
and if degraded service is detected, apply goodwill credit and explain findings to the user.
"""


class SupportAgentState(TypedDict):
    """LangGraph State definition with append-only message log."""
    messages: Annotated[Sequence[BaseMessage], operator.add]
    agent_step: int


def build_telecom_agent(
    checkpointer: Optional[BaseCheckpointSaver] = None,
    model_provider: str = "openai",
    model_name: str = "gpt-4o-mini",
):
    """Assembles and compiles the LangGraph state machine with persistence."""
    tools = [lookup_telecom_account, diagnose_network_cell, apply_retention_credit]
    model = get_chat_model(model_provider, model=model_name, temperature=0.0).bind_tools(tools)

    def agent_node(state: SupportAgentState) -> dict:
        current_step = state.get("agent_step", 0) + 1
        messages = state["messages"]

        # Ensure system prompt is present at head
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=SYSTEM_AGENT_PROMPT)] + list(messages)

        response = model.invoke(messages)
        return {"messages": [response], "agent_step": current_step}

    # Construct Cyclical State Graph
    builder = StateGraph(SupportAgentState)

    builder.add_node("agent", agent_node)
    builder.add_node("tools", ToolNode(tools))

    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", tools_condition)
    builder.add_edge("tools", "agent")

    # Compile with checkpointer for state persistence, recovery, and time travel
    return builder.compile(checkpointer=checkpointer)

