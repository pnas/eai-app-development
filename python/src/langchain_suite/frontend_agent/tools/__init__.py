"""Tools package for frontend agent showcase."""

from src.langchain_suite.frontend_agent.tools.default_tools import (
    get_current_time,
    get_random_quote,
)
from src.langchain_suite.frontend_agent.tools.document_retrieval import (
    list_eu_documents,
    search_eu_guidelines,
    read_eu_article_or_section,
)
from src.langchain_suite.frontend_agent.tools.registry import (
    ToolRegistry,
    GLOBAL_TOOL_REGISTRY,
)

__all__ = [
    "get_current_time",
    "get_random_quote",
    "list_eu_documents",
    "search_eu_guidelines",
    "read_eu_article_or_section",
    "ToolRegistry",
    "GLOBAL_TOOL_REGISTRY",
]

