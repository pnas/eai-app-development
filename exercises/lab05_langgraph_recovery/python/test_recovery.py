"""Test suite for Lab 05: LangGraph Resilient State Machine & SQLite Crash Recovery."""

import os
import sys
import sqlite3
from pathlib import Path
from typing import Any, Dict, List

# Add project root to sys.path
root_dir = Path(__file__).resolve().parents[3]
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.sqlite import SqliteSaver

from exercises.lab05_langgraph_recovery.python.solution import (
    build_agent_graph as build_agent_graph_sol,
    resume_agent_workflow as resume_agent_workflow_sol,
    ResilientAgentState as ResilientAgentStateSol,
)


class DeterministicMockAgentModel(BaseChatModel):
    """Deterministic Mock LLM that generates a tool call on turn 1 and final message on turn 2."""

    turn_count: int = 0

    @property
    def _llm_type(self) -> str:
        return "deterministic_mock"

    def bind_tools(self, tools: Any, **kwargs: Any) -> Any:
        return self

    def _generate(self, messages: List[Any], stop: Any = None, **kwargs: Any) -> ChatResult:
        # Check if last message is a ToolMessage (meaning tool executed)
        if any(isinstance(m, ToolMessage) for m in messages):
            text = "I have confirmed your subscriber account is active with plan 5G-Max."
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content=text))])
        else:
            # Generate tool call to query_subscriber
            tool_call = {
                "name": "query_subscriber",
                "args": {"account_id": "ACCT-99"},
                "id": "call_mock_123",
            }
            ai_msg = AIMessage(content="", tool_calls=[tool_call])
            return ChatResult(generations=[ChatGeneration(message=ai_msg)])


@pytest.fixture
def test_db_path(tmp_path):
    """Creates a temporary sqlite database file."""
    return str(tmp_path / "test_checkpoints.db")


def test_solution_full_tool_cycle_and_persistence(test_db_path):
    """Verifies that the agent executes tools and persists checkpoints to SQLite."""
    conn = sqlite3.connect(test_db_path, check_same_thread=False)
    saver = SqliteSaver(conn)
    saver.setup()

    mock_llm = DeterministicMockAgentModel()
    agent = build_agent_graph_sol(mock_llm, checkpointer=saver)

    thread_id = "test-session-001"
    config = {"configurable": {"thread_id": thread_id}}

    initial_input = {"messages": [HumanMessage(content="Check my account ACCT-99")]}
    result = agent.invoke(initial_input, config=config)

    # Verify conversation completed with ToolMessage and final AIMessage
    messages = result["messages"]
    assert any(isinstance(m, ToolMessage) for m in messages)
    assert messages[-1].content == "I have confirmed your subscriber account is active with plan 5G-Max."

    # Verify SQLite checkpoints written
    cursor = conn.cursor()
    cursor.execute("SELECT count(*) FROM checkpoints WHERE thread_id = ?", (thread_id,))
    count = cursor.fetchone()[0]
    assert count >= 3  # Initial input, tool execution, agent final response

    conn.close()


def test_solution_crash_rehydration_and_resume(test_db_path):
    """Simulates a worker crash, rehydration of SQLite state, and resume without repetition."""
    thread_id = "test-crash-session-777"
    config = {"configurable": {"thread_id": thread_id}}

    # Phase 1: Run Turn 1 and kill process
    conn1 = sqlite3.connect(test_db_path, check_same_thread=False)
    saver1 = SqliteSaver(conn1)
    saver1.setup()

    mock_llm = DeterministicMockAgentModel()
    agent1 = build_agent_graph_sol(mock_llm, checkpointer=saver1)
    agent1.invoke({"messages": [HumanMessage(content="First turn")]}, config=config)

    conn1.close()
    del agent1
    del saver1

    # Phase 2: Boot new instance and rehydrate
    conn2 = sqlite3.connect(test_db_path, check_same_thread=False)
    saver2 = SqliteSaver(conn2)
    agent2 = build_agent_graph_sol(mock_llm, checkpointer=saver2)

    saved_state = agent2.get_state(config)
    assert saved_state is not None
    assert len(saved_state.values["messages"]) >= 3

    # Phase 3: Resume with follow-up
    resumed = resume_agent_workflow_sol(agent2, thread_id, followup_message="Thank you, goodbye.")
    assert resumed["messages"][-1].content is not None
    assert len(resumed["messages"]) > len(saved_state.values["messages"])

    conn2.close()

