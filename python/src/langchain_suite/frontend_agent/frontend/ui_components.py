"""UI Components and Sidebar controls for the Streamlit Agent Showcase."""

from __future__ import annotations

import os
import uuid
from typing import Any, Dict, List
import streamlit as st

from src.langchain_suite.core.env import get_configured_providers, load_workspace_env
from src.langchain_suite.frontend_agent.frontend.client_remote_sse import RemoteSseAgentClient
from src.langchain_suite.frontend_agent.tools.registry import GLOBAL_TOOL_REGISTRY

load_workspace_env()

MODE_IN_PROCESS = "Pattern A: In-Process Monolith (Local)"
MODE_REMOTE_SSE = "Pattern B: Decoupled Backend (FastAPI + SSE)"


def init_session_state() -> None:
    """Initialize session state variables."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "session_id" not in st.session_state:
        st.session_state.session_id = f"session-{uuid.uuid4().hex[:8]}"


def render_sidebar() -> Dict[str, Any]:
    """Renders the configuration sidebar and returns selected runtime parameters."""
    st.sidebar.title("⚙️ Architecture Setup")

    default_mode_env = os.environ.get("STREAMLIT_AGENT_MODE", "").lower()
    default_index = 1 if default_mode_env in ("remote", "decoupled", "backend", "sse") else 0

    # 1. Architecture Mode Selection
    mode = st.sidebar.radio(
        "Integration Architecture",
        [MODE_IN_PROCESS, MODE_REMOTE_SSE],
        index=default_index,
        help=(
            "Pattern A runs the LangChain agent in the same process as Streamlit. "
            "Pattern B connects over HTTP/SSE to a separate FastAPI agent microservice."
        ),
    )

    env_backend_url = os.environ.get("AGENT_BACKEND_URL", "http://localhost:8000")
    backend_url = env_backend_url
    if mode == MODE_REMOTE_SSE:
        st.sidebar.markdown("---")
        st.sidebar.subheader("🌐 Remote Backend")
        backend_url = st.sidebar.text_input("FastAPI Base URL", value=env_backend_url)

        # Health Probe
        client = RemoteSseAgentClient(base_url=backend_url)
        col1, col2 = st.sidebar.columns([3, 2])
        with col1:
            try:
                health = client.check_health()
                st.sidebar.success(f"🟢 Backend Online (Tools: {len(health.get('available_tools', []))})")
            except Exception:
                st.sidebar.error("🔴 Backend Offline (Run FastAPI server)")

    st.sidebar.markdown("---")
    st.sidebar.subheader("🤖 LLM Provider")

    providers_ready = get_configured_providers()
    provider_options = ["mock", "openai", "anthropic", "gemini"]
    default_provider = os.environ.get("AGENT_DEFAULT_PROVIDER", "mock").lower()
    provider_index = provider_options.index(default_provider) if default_provider in provider_options else 0
    provider = st.sidebar.selectbox(
        "Provider",
        provider_options,
        index=provider_index,
        help="Select 'mock' for offline execution without API keys, or select an enterprise provider.",
    )

    if provider != "mock":
        if providers_ready.get(provider, False):
            st.sidebar.caption(f"🟢 **{provider.upper()}_API_KEY** detected")
        else:
            st.sidebar.warning(f"⚠️ **{provider.upper()}_API_KEY** missing in .env")

    model_name = None
    if provider == "openai":
        model_name = st.sidebar.text_input("OpenAI Model", value="gpt-4.1-mini")
    elif provider == "anthropic":
        model_name = st.sidebar.text_input("Anthropic Model", value="claude-haiku-5-5")
    elif provider == "gemini":
        model_name = st.sidebar.text_input("Gemini Model", value="gemini-3.8-flash")

    # Tool Catalog Viewer
    st.sidebar.markdown("---")
    with st.sidebar.expander("🛠️ Tool Inventory (V1)", expanded=False):
        tools = GLOBAL_TOOL_REGISTRY.get_metadata()
        for t in tools:
            st.markdown(f"**`{t['name']}`**")
            st.caption(t["description"])
            if t.get("args_schema", {}).get("properties"):
                props = list(t["args_schema"]["properties"].keys())
                st.code(f"Args: {', '.join(props)}", language="text")
            st.divider()

    # Session Controls
    st.sidebar.markdown("---")
    st.sidebar.caption(f"Session Thread ID: `{st.session_state.session_id}`")
    if st.sidebar.button("🧹 Clear Chat History", use_container_width=True):
        st.session_state.messages = []
        st.session_state.session_id = f"session-{uuid.uuid4().hex[:8]}"
        st.rerun()

    return {
        "mode": mode,
        "backend_url": backend_url,
        "provider": provider,
        "model": model_name,
        "session_id": st.session_state.session_id,
    }

