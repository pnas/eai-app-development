"""Test suite for Simple Document Retrieval Engine (Strictly NOT RAG)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.langchain_suite.frontend_agent.backend.server import app
from src.langchain_suite.frontend_agent.tools.document_retrieval import (
    EuAiActDocumentStore,
    list_eu_documents,
    search_eu_guidelines,
    read_eu_article_or_section,
)
from src.langchain_suite.frontend_agent.tools.registry import GLOBAL_TOOL_REGISTRY


def test_document_store_indexing():
    """Verify in-memory PDF indexing correctly parses the 3 EU AI Act PDFs."""
    store = EuAiActDocumentStore.get_instance()
    store.ensure_indexed()

    assert "definition_guidelines" in store.documents
    assert "prohibited_practices" in store.documents
    assert "ai_act_regulation" in store.documents

    def_doc = store.documents["definition_guidelines"]
    assert def_doc.page_count >= 10, f"Expected >= 10 pages, got {def_doc.page_count}"

    prohib_doc = store.documents["prohibited_practices"]
    assert prohib_doc.page_count >= 100, f"Expected >= 100 pages, got {prohib_doc.page_count}"

    reg_doc = store.documents["ai_act_regulation"]
    assert reg_doc.page_count >= 140, f"Expected >= 140 pages, got {reg_doc.page_count}"


def test_list_eu_documents_tool():
    """Verify list_eu_documents returns formatted markdown catalog."""
    catalog = list_eu_documents.invoke({})
    assert "definition_guidelines" in catalog
    assert "prohibited_practices" in catalog
    assert "ai_act_regulation" in catalog
    assert "pages" in catalog.lower()


def test_search_eu_guidelines_tool():
    """Verify search_eu_guidelines returns matches with citations and page numbers."""
    res = search_eu_guidelines.invoke({"query": "biometric categorization prohibited"})
    assert "Source Document:" in res
    assert "Citation: Page" in res
    assert "Excerpt:" in res


def test_read_eu_article_or_section_tool():
    """Verify read_eu_article_or_section retrieves Article 5 with page 51 citation."""
    res = read_eu_article_or_section.invoke({
        "doc_id": "ai_act_regulation",
        "section_name": "Article 5",
    })
    assert "Official Citation: Regulation (EU) 2024/1689" in res
    assert "Page 51" in res
    assert "Prohibited AI practices" in res
    assert "subliminal techniques" in res


def test_tools_registered_in_global_registry():
    """Verify document retrieval tools are cataloged in GLOBAL_TOOL_REGISTRY."""
    tool_names = [t.name for t in GLOBAL_TOOL_REGISTRY.get_all()]
    assert "list_eu_documents" in tool_names
    assert "search_eu_guidelines" in tool_names
    assert "read_eu_article_or_section" in tool_names


def test_fastapi_sse_document_retrieval_stream():
    """Verify decoupled FastAPI SSE streams document retrieval tool execution."""
    client = TestClient(app)
    payload = {
        "prompt": "What AI practices are prohibited under Article 5 of the EU AI Act?",
        "provider": "mock",
        "thread_id": "test-doc-sse-1",
    }

    with client.stream("POST", "/agent/chat/stream", json=payload) as resp:
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")

        events = []
        for line in resp.iter_lines():
            if line.startswith("event:"):
                events.append(line.replace("event:", "").strip())

        assert "tool_start" in events
        assert "tool_end" in events
        assert "token" in events
        assert "done" in events
