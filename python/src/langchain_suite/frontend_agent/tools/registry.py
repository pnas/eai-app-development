"""Extensible Tool Registry for the Frontend Agent Showcase.

Enables dynamic registration, retrieval, and schema inspection of tools
so instructors and students can easily add new domain tools without
altering the core agent or API contracts.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from langchain_core.tools import BaseTool
from src.langchain_suite.frontend_agent.tools.default_tools import (
    get_current_time,
    get_random_quote,
)
from src.langchain_suite.frontend_agent.tools.document_retrieval import (
    list_eu_documents,
    search_eu_guidelines,
    read_eu_article_or_section,
)


class ToolRegistry:
    """Thread-safe catalog of tools available to LangChain/LangGraph agents."""

    def __init__(self, initial_tools: Optional[List[BaseTool]] = None):
        self._tools: Dict[str, BaseTool] = {}
        defaults = (
            initial_tools
            if initial_tools is not None
            else [
                get_current_time,
                get_random_quote,
                list_eu_documents,
                search_eu_guidelines,
                read_eu_article_or_section,
            ]
        )
        for t in defaults:
            self.register(t)

    def register(self, tool_instance: BaseTool) -> None:
        """Register a new LangChain tool."""
        self._tools[tool_instance.name] = tool_instance

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Retrieve a registered tool by its name."""
        return self._tools.get(name)

    def get_all(self) -> List[BaseTool]:
        """Return a list of all registered tools."""
        return list(self._tools.values())

    def get_metadata(self) -> List[Dict[str, Any]]:
        """Return JSON-serializable tool metadata (name, description, schema)."""
        metadata = []
        for name, tool_obj in self._tools.items():
            metadata.append({
                "name": name,
                "description": tool_obj.description,
                "args_schema": (
                    tool_obj.args_schema.model_json_schema()
                    if tool_obj.args_schema
                    else {}
                ),
            })
        return metadata


# Global singleton registry instance
GLOBAL_TOOL_REGISTRY = ToolRegistry()

