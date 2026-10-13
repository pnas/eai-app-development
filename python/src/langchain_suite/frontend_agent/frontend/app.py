"""Main Streamlit Chat Application demonstrating Dual LangChain Agent Integrations.

Patterns demonstrated:
1. Pattern A: In-Process Monolith (Agent executes in the same Python process).
2. Pattern B: Decoupled Microservice (Agent runs in FastAPI, streams over SSE).
"""

from __future__ import annotations

import streamlit as st

from src.langchain_suite.frontend_agent.frontend.client_in_process import run_in_process_stream
from src.langchain_suite.frontend_agent.frontend.client_remote_sse import RemoteSseAgentClient
from src.langchain_suite.frontend_agent.frontend.ui_components import (
    MODE_IN_PROCESS,
    MODE_REMOTE_SSE,
    init_session_state,
    render_sidebar,
)

# Page configuration
st.set_page_config(
    page_title="Streamlit Agent Integrations (In-Process vs Remote SSE)",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize conversation and session state
init_session_state()

# Render configuration sidebar
config = render_sidebar()

# Main Header Banner
st.title("🤖 LangChain Agent Frontend Integration Showcase")
st.markdown(
    """
This application demonstrates **two fundamental architectural patterns** for integrating 
LangChain/LangGraph tool-calling agents into frontend user interfaces:
- **Pattern A (In-Process Monolith)**: The agent runs inside the Streamlit worker process with zero network hops.
- **Pattern B (Decoupled Microservice)**: An independent FastAPI service executes the agent and streams lifecycle events over **Server-Sent Events (SSE)**.
    """
)

# Active Architecture Indicator
if config["mode"] == MODE_IN_PROCESS:
    st.info("🔹 **Active Mode:** Pattern A — Monolithic In-Process Execution (`local thread runner`)")
else:
    st.success(f"🌐 **Active Mode:** Pattern B — Decoupled Microservice (`HTTP/SSE via {config['backend_url']}`)")

# EU AI Act Document Resources Inspector (Simple Retrieval - NOT RAG)
with st.expander("📑 Source Regulatory Documents (Simple Retrieval — Strictly NOT RAG)", expanded=False):
    st.markdown(
        """
This decoupled agent features **deterministic document retrieval** directly over the official EU AI Act
documents stored in `docs/resources`. **No vector databases, embeddings, or chunk-splitting are used**:
1. **Commission Guidelines on Definition of an AI System** (`C(2025) 5053 final` - 13 pages)
2. **Commission Guidelines on Prohibited AI Practices** (`C(2025) 5052 final` - 134 pages)
3. **Regulation (EU) 2024/1689 (EU AI Act Full Text)** (`OJ L 2024/1689` - 144 pages)
        """
    )
    col1, col2, col3 = st.columns(3)
    with col1:
        st.caption("📘 **Definition Guidelines**\n13 pages • C(2025) 5053")
    with col2:
        st.caption("📕 **Prohibited Practices**\n134 pages • C(2025) 5052")
    with col3:
        st.caption("📗 **Full Regulation**\n144 pages • OJ L 2024/1689")

# Suggested Quick Prompt Buttons
st.markdown("**Suggested Questions:**")
q_cols = st.columns(3)
clicked_prompt = None
with q_cols[0]:
    if st.button("🚫 What AI practices are prohibited under Article 5?", use_container_width=True):
        clicked_prompt = "What AI practices are prohibited under Article 5 of the EU AI Act?"
with q_cols[1]:
    if st.button("⚖️ How is an AI system defined?", use_container_width=True):
        clicked_prompt = "How does the Commission define an AI system in the guidelines?"
with q_cols[2]:
    if st.button("📜 List available EU AI Act documents", use_container_width=True):
        clicked_prompt = "List available EU AI Act documents in the repository."

st.divider()

# Render Conversation History
for msg in st.session_state.messages:
    role = msg.get("role", "user")
    with st.chat_message(role):
        # Display any tool calls recorded for this step
        if "tools_used" in msg and msg["tools_used"]:
            with st.expander("🛠️ Tools Executed & Citations", expanded=False):
                for t in msg["tools_used"]:
                    st.markdown(f"**Tool:** `{t.get('tool')}`")
                    st.caption(f"Input: `{t.get('input')}`")
                    st.text(f"Output: {t.get('output')}")
        st.markdown(msg.get("content", ""))

# Chat Input & Streaming Execution
chat_input = st.chat_input("Ask a question, e.g. 'What is prohibited in Article 5?' or 'What time is it in Tokyo?'...")
user_prompt = clicked_prompt or chat_input

if user_prompt:
    # 1. Display user prompt immediately
    with st.chat_message("user"):
        st.markdown(user_prompt)

    # Append user prompt to session state
    st.session_state.messages.append({"role": "user", "content": user_prompt})

    # Prepare historical context for multi-turn reasoning
    history_payload = [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state.messages
    ]

    # 2. Execute agent stream in assistant message container
    with st.chat_message("assistant"):
        text_placeholder = st.empty()
        status_container = st.container()

        accumulated_text = ""
        tools_executed = []
        active_status_widget = None

        # Choose streaming client based on selected architecture pattern
        if config["mode"] == MODE_IN_PROCESS:
            event_stream = run_in_process_stream(
                prompt=user_prompt,
                messages=history_payload,
                provider=config["provider"],
                model=config["model"],
                thread_id=config["session_id"],
            )
        else:
            client = RemoteSseAgentClient(base_url=config["backend_url"])
            event_stream = client.stream_chat(
                prompt=user_prompt,
                messages=history_payload,
                provider=config["provider"],
                model=config["model"],
                thread_id=config["session_id"],
            )

        # Iterate through normalized lifecycle events
        for event in event_stream:
            event_type = event.get("event")

            # A. Tool Execution Started
            if event_type == "tool_start":
                tool_name = event.get("tool", "tool")
                tool_input = event.get("input", {})
                active_status_widget = status_container.status(
                    f"⚙️ Running tool: `{tool_name}`...",
                    expanded=True,
                )
                active_status_widget.write(f"**Arguments:** `{tool_input}`")
                tools_executed.append({"tool": tool_name, "input": tool_input, "output": ""})

            # B. Tool Execution Finished
            elif event_type == "tool_end":
                tool_name = event.get("tool", "tool")
                tool_output = event.get("output", "")
                if tools_executed and tools_executed[-1]["tool"] == tool_name:
                    tools_executed[-1]["output"] = tool_output
                if active_status_widget:
                    active_status_widget.write(f"**Result:** {tool_output}")
                    active_status_widget.update(
                        label=f"✅ Tool `{tool_name}` completed",
                        state="complete",
                        expanded=False,
                    )

            # C. Token Chunks
            elif event_type == "token":
                chunk = event.get("content", "")
                accumulated_text += chunk
                text_placeholder.markdown(accumulated_text + "▌")

            # D. Error Event
            elif event_type == "error":
                st.error(f"❌ Error: {event.get('error')}")

            # E. Stream Complete
            elif event_type == "done":
                break

        # Finalize display without trailing cursor
        text_placeholder.markdown(accumulated_text)

        # Save assistant turn to conversation state
        st.session_state.messages.append({
            "role": "assistant",
            "content": accumulated_text,
            "tools_used": tools_executed,
        })

