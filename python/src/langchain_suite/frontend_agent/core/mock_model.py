"""Deterministic Mock Chat Model for offline testing and educational demonstrations.

Allows running the full Streamlit UI + SSE streaming pipeline without requiring
active OpenAI, Anthropic, or Gemini API keys.
"""

from __future__ import annotations

import json
import re
from typing import Any, AsyncIterator, Iterator, List, Optional
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    HumanMessage,
    ToolMessage,
)
from langchain_core.outputs import (
    ChatGeneration,
    ChatGenerationChunk,
    ChatResult,
)


class MockAgentChatModel(BaseChatModel):
    """Simulated tool-calling ChatModel for offline student labs & UI testing."""

    model_name: str = "mock-agent-v1"

    @property
    def _llm_type(self) -> str:
        return "mock-agent-chat-model"

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> MockAgentChatModel:
        return self

    def _determine_action(self, messages: List[BaseMessage]) -> tuple[Optional[dict], str]:
        """Inspects messages to decide whether to trigger a tool call or deliver final text."""
        # Check if the last message is a ToolMessage (tool already executed)
        if messages and isinstance(messages[-1], ToolMessage):
            tool_msg = messages[-1]
            content = str(tool_msg.content)
            # If EU AI Act tool was executed, provide a structured cited summary
            if "Official Citation:" in content or "EU AI Act" in content or "Regulation (EU)" in content:
                return None, (
                    f"### 📋 EU AI Act Retrieval Result\n\n"
                    f"{content}\n\n"
                    f"*Source: Official EU Regulatory Documents (docs/resources)*"
                )
            return None, (
                f"I processed the tool output: {content}\n\n"
                "Is there anything else you'd like to check?"
            )

        # Find the latest user message
        user_text = ""
        for m in reversed(messages):
            if isinstance(m, HumanMessage) or (hasattr(m, "type") and m.type == "human"):
                user_text = str(m.content).lower()
                break

        # Check for EU AI Act document catalog trigger
        if any(w in user_text for w in ("list doc", "available doc", "which doc", "what doc", "resources", "catalog")):
            return {
                "name": "list_eu_documents",
                "args": {},
                "id": "mock_call_list_docs_1",
            }, ""

        # Check for Article 5 / Prohibited AI practices trigger
        if "article 5" in user_text or "prohibit" in user_text:
            return {
                "name": "read_eu_article_or_section",
                "args": {"doc_id": "ai_act_regulation", "section_name": "Article 5"},
                "id": "mock_call_article_5_1",
            }, ""

        # Check for AI system definition trigger
        if "definition" in user_text or "define" in user_text:
            return {
                "name": "search_eu_guidelines",
                "args": {"query": "definition of an AI system", "doc_id": "definition_guidelines"},
                "id": "mock_call_def_1",
            }, ""

        # Check for general EU AI Act or regulatory query
        if any(w in user_text for w in ("eu ai", "ai act", "regulation", "high risk", "transparency", "gpai", "guideline")):
            return {
                "name": "search_eu_guidelines",
                "args": {"query": user_text[:80]},
                "id": "mock_call_search_1",
            }, ""

        # Check for time tool trigger
        if any(w in user_text for w in ("time", "clock", "date", "hour", "now", "timezone")):
            tz = "UTC"
            if "berlin" in user_text or "germany" in user_text:
                tz = "Europe/Berlin"
            elif "new york" in user_text or "ny" in user_text:
                tz = "America/New_York"
            elif "tokyo" in user_text or "japan" in user_text:
                tz = "Asia/Tokyo"
            elif "athens" in user_text or "greece" in user_text:
                tz = "Europe/Athens"
            elif "london" in user_text or "uk" in user_text:
                tz = "Europe/London"

            return {
                "name": "get_current_time",
                "args": {"timezone": tz},
                "id": "mock_call_time_1",
            }, ""

        # Check for quote tool trigger
        if any(w in user_text for w in ("quote", "inspire", "inspiration", "wisdom", "motto", "saying")):
            category = "general"
            if "tech" in user_text or "software" in user_text or "code" in user_text:
                category = "technology"
            elif "philo" in user_text or "life" in user_text:
                category = "philosophy"
            elif "motivat" in user_text or "success" in user_text:
                category = "motivation"
            elif "sci" in user_text:
                category = "science"

            return {
                "name": "get_random_quote",
                "args": {"category": category},
                "id": "mock_call_quote_1",
            }, ""

        # Default conversational response
        return None, (
            "Hello! I am your AI assistant equipped with real-time tools and deterministic EU AI Act retrieval.\n"
            "You can ask me:\n"
            "- 'What AI practices are prohibited under Article 5?'\n"
            "- 'How does the EU define an AI system?'\n"
            "- 'List available EU AI Act documents'\n"
            "- Or standard tools: 'What time is it in Berlin?' / 'Give me an inspiring quote'"
        )

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        tool_call, reply_text = self._determine_action(messages)

        if tool_call:
            message = AIMessage(
                content="",
                tool_calls=[{
                    "name": tool_call["name"],
                    "args": tool_call["args"],
                    "id": tool_call["id"],
                }],
            )
        else:
            message = AIMessage(content=reply_text)

        return ChatResult(generations=[ChatGeneration(message=message)])

    def _stream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        tool_call, reply_text = self._determine_action(messages)

        if tool_call:
            chunk = AIMessageChunk(
                content="",
                tool_call_chunks=[{
                    "name": tool_call["name"],
                    "args": json.dumps(tool_call["args"]),
                    "id": tool_call["id"],
                    "index": 0,
                }],
            )
            yield ChatGenerationChunk(message=chunk)
        else:
            # Stream tokens
            words = re.findall(r"\S+|\s+", reply_text)
            for word in words:
                if run_manager:
                    run_manager.on_llm_new_token(word)
                yield ChatGenerationChunk(message=AIMessageChunk(content=word))

