"""Simple Document Retrieval Engine (Strictly NOT RAG) for EU AI Act Documents.

Provides deterministic, citation-backed document inspection across official EU AI Act
publications stored in docs/resources:
1. Commission Guidelines on the definition of an AI system (C(2025) 5053 final)
2. Commission Guidelines on prohibited AI practices (C(2025) 5052 final)
3. Regulation (EU) 2024/1689 Official Journal text (OJ L 2024/1689)

Architectural Note:
This is strictly NOT RAG:
- Zero vector databases (Chroma, FAISS, Pinecone)
- Zero embedding models or dense vector cosine similarity
- Deterministic page-indexed lexical & section retrieval with exact page citations
"""

from __future__ import annotations

import os
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from langchain_core.tools import tool
from pypdf import PdfReader


@dataclass
class IndexedPage:
    page_number: int  # 1-indexed
    text: str
    sections: List[str] = field(default_factory=list)


@dataclass
class IndexedDocument:
    doc_id: str
    title: str
    filename: str
    page_count: int
    pages: List[IndexedPage] = field(default_factory=list)
    section_index: Dict[str, List[int]] = field(default_factory=dict)  # section_name -> list of page_numbers


class EuAiActDocumentStore:
    """Thread-safe in-memory indexer and retrieval engine for EU AI Act documents."""

    _instance: Optional[EuAiActDocumentStore] = None
    _lock = threading.Lock()

    def __init__(self, resources_dir: Optional[str] = None):
        self.resources_dir = resources_dir or self._find_resources_dir()
        self.documents: Dict[str, IndexedDocument] = {}
        self._is_indexed = False

    @classmethod
    def get_instance(cls) -> EuAiActDocumentStore:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @staticmethod
    def _find_resources_dir() -> str:
        """Locates the docs/resources directory relative to the repository root."""
        env_dir = os.environ.get("RESOURCES_DIR")
        if env_dir and os.path.isdir(env_dir):
            return env_dir
        current = Path(__file__).resolve()
        for parent in [current] + list(current.parents):
            candidate = parent / "docs" / "resources"
            if candidate.exists() and candidate.is_dir():
                return str(candidate)
        return str(Path.cwd() / "docs" / "resources")

    @staticmethod
    def _safe_windows_path(path_str: str) -> str:
        """Appends Windows extended path prefix \\?\\ to safely bypass MAX_PATH limits."""
        abs_path = os.path.abspath(path_str)
        if os.name == "nt" and not abs_path.startswith("\\\\?\\"):
            return f"\\\\?\\{abs_path}"
        return abs_path

    def ensure_indexed(self) -> None:
        """Loads and indexes the 3 EU AI Act PDFs if not already cached."""
        if self._is_indexed:
            return

        with self._lock:
            if self._is_indexed:
                return

            safe_res_dir = self._safe_windows_path(self.resources_dir)
            if not os.path.exists(safe_res_dir):
                return

            for fname in sorted(os.listdir(safe_res_dir)):
                if not fname.lower().endswith(".pdf"):
                    continue

                full_path = os.path.join(safe_res_dir, fname)
                doc_id, title = self._resolve_doc_metadata(fname)
                indexed_doc = self._parse_pdf(doc_id, title, fname, full_path)
                self.documents[doc_id] = indexed_doc

            self._is_indexed = True

    def _resolve_doc_metadata(self, fname: str) -> Tuple[str, str]:
        fname_lower = fname.lower()
        if "definition" in fname_lower:
            return (
                "definition_guidelines",
                "Commission Guidelines on the Definition of an AI System (C(2025) 5053 final)",
            )
        elif "prohibited" in fname_lower:
            return (
                "prohibited_practices",
                "Commission Guidelines on Prohibited AI Practices (C(2025) 5052 final)",
            )
        elif "1689" in fname_lower or "oj_l" in fname_lower:
            return (
                "ai_act_regulation",
                "Regulation (EU) 2024/1689 (EU AI Act Full Text - OJ L 2024/1689)",
            )
        else:
            clean_name = os.path.splitext(fname)[0].replace("_", " ")
            return (clean_name.lower().replace(" ", "_")[:30], clean_name)

    def _parse_pdf(self, doc_id: str, title: str, filename: str, full_path: str) -> IndexedDocument:
        try:
            reader = PdfReader(full_path)
        except Exception:
            # Fallback if corrupted or inaccessible
            return IndexedDocument(doc_id=doc_id, title=title, filename=filename, page_count=0)

        pages: List[IndexedPage] = []
        section_index: Dict[str, List[int]] = {}

        # Standalone substantive article heading pattern, e.g. "Article 5\n" or "Article 5 "
        substantive_article_pattern = re.compile(r"^\s*(Article\s+\d+[a-z]?)\b\s*$", re.MULTILINE | re.IGNORECASE)
        inline_article_pattern = re.compile(r"\b(Article\s+\d+[a-z]?)\b", re.IGNORECASE)
        section_pattern = re.compile(r"^(?:Section\s+\d+|[1-9]\.[0-9]+(?:\.[0-9]+)?)\s+([A-Z][^\n]{3,60})", re.MULTILINE)

        for i, page in enumerate(reader.pages):
            p_num = i + 1
            raw_text = page.extract_text() or ""
            detected_sections: List[str] = []

            # Prioritize substantive standalone article headers
            for match in substantive_article_pattern.finditer(raw_text):
                art = match.group(1).title()
                if art not in detected_sections:
                    detected_sections.append(art)
                # Standalone headings take first priority in section index
                section_index.setdefault(art.lower(), []).insert(0, p_num)

            # Detect other article mentions
            for match in inline_article_pattern.finditer(raw_text):
                art = match.group(1).title()
                if art not in detected_sections:
                    detected_sections.append(art)
                if p_num not in section_index.setdefault(art.lower(), []):
                    section_index[art.lower()].append(p_num)

            # Detect Section Headings
            for match in section_pattern.finditer(raw_text):
                sec = match.group(0).strip()
                if sec not in detected_sections:
                    detected_sections.append(sec)
                section_index.setdefault(sec.lower(), []).append(p_num)

            pages.append(IndexedPage(page_number=p_num, text=raw_text, sections=detected_sections))

        return IndexedDocument(
            doc_id=doc_id,
            title=title,
            filename=filename,
            page_count=len(pages),
            pages=pages,
            section_index=section_index,
        )

    def search(
        self,
        query: str,
        doc_id: Optional[str] = None,
        max_results: int = 4,
    ) -> List[Dict[str, Any]]:
        """Performs deterministic keyword and section lookup across the documents."""
        self.ensure_indexed()

        query_clean = query.strip().lower()
        query_terms = [t for t in re.split(r"\W+", query_clean) if len(t) > 2]
        if not query_terms:
            return []

        targets = [self.documents[doc_id]] if (doc_id and doc_id in self.documents) else list(self.documents.values())
        matches: List[Dict[str, Any]] = []

        for doc in targets:
            for page in doc.pages:
                text_lower = page.text.lower()
                # Count matching terms
                score = sum(text_lower.count(t) for t in query_terms)
                # Boost if query matches a detected section or Article
                for sec in page.sections:
                    if any(t in sec.lower() for t in query_terms):
                        score += 25

                if score > 0:
                    # Extract best snippet around first matching term
                    first_pos = -1
                    for t in query_terms:
                        pos = text_lower.find(t)
                        if pos != -1 and (first_pos == -1 or pos < first_pos):
                            first_pos = pos

                    start = max(0, first_pos - 100)
                    end = min(len(page.text), first_pos + 400)
                    snippet = page.text[start:end].replace("\n", " ").strip()

                    matches.append({
                        "doc_id": doc.doc_id,
                        "doc_title": doc.title,
                        "page_number": page.page_number,
                        "sections": page.sections,
                        "score": score,
                        "snippet": f"...{snippet}..." if start > 0 else f"{snippet}...",
                    })

        matches.sort(key=lambda x: x["score"], reverse=True)
        return matches[:max_results]

    def read_section(
        self,
        doc_id: str,
        section_name: str,
        max_chars: int = 2800,
    ) -> Dict[str, Any]:
        """Deterministically retrieves the text of a specific article or section."""
        self.ensure_indexed()

        if doc_id not in self.documents:
            return {
                "found": False,
                "error": f"Document '{doc_id}' not found. Available: {list(self.documents.keys())}",
            }

        doc = self.documents[doc_id]
        sec_clean = section_name.strip().lower()

        # Check section index
        matched_pages: List[int] = []
        # First exact key match
        if sec_clean in doc.section_index:
            matched_pages.extend(doc.section_index[sec_clean])
        else:
            for indexed_sec, p_nums in doc.section_index.items():
                if sec_clean in indexed_sec:
                    matched_pages.extend(p_nums)

        if not matched_pages:
            # Fallback: scan full text for the section term
            for page in doc.pages:
                if sec_clean in page.text.lower():
                    matched_pages.append(page.page_number)

        if not matched_pages:
            return {
                "found": False,
                "doc_id": doc_id,
                "doc_title": doc.title,
                "error": f"Section '{section_name}' not found in {doc.title}.",
            }

        # Deduplicate while preserving order
        seen = set()
        deduped_pages = [p for p in matched_pages if not (p in seen or seen.add(p))]
        first_page = deduped_pages[0]
        extracted_text = ""

        # Extract text from the matched page and possibly the next page
        for p_num in deduped_pages[:2]:
            p_obj = doc.pages[p_num - 1]
            extracted_text += f"\n--- Page {p_num} ---\n" + p_obj.text

        # Locate section start in text
        pos = extracted_text.lower().find(sec_clean)
        if pos != -1:
            content = extracted_text[pos : pos + max_chars]
        else:
            content = extracted_text[:max_chars]

        return {
            "found": True,
            "doc_id": doc_id,
            "doc_title": doc.title,
            "primary_page": first_page,
            "all_matching_pages": deduped_pages,
            "section_name": section_name,
            "content": content.strip(),
        }


# Global store instance
_DOCUMENT_STORE = EuAiActDocumentStore.get_instance()


@tool
def list_eu_documents() -> str:
    """Catalog all official EU AI Act regulatory documents available in the repository.

    Returns the document ID, official title, file name, and total page count.
    Use this tool first to discover valid document IDs for subsequent searches.
    """
    _DOCUMENT_STORE.ensure_indexed()
    if not _DOCUMENT_STORE.documents:
        return "No documents found in docs/resources."

    lines = ["Available EU AI Act Documents (docs/resources):"]
    for doc in _DOCUMENT_STORE.documents.values():
        lines.append(
            f"- ID: `{doc.doc_id}`\n"
            f"  Title: {doc.title}\n"
            f"  Filename: {doc.filename}\n"
            f"  Pages: {doc.page_count} pages\n"
        )
    return "\n".join(lines)


@tool
def search_eu_guidelines(query: str, doc_id: Optional[str] = None) -> str:
    """Search the EU AI Act documents for specific regulatory concepts or questions.

    Args:
        query: Specific regulatory search query (e.g. 'prohibited practices', 'biometric categorization',
               'definition of AI system', 'Article 5', 'high risk AI', 'transparency').
        doc_id: Optional document ID to filter search ('definition_guidelines', 'prohibited_practices',
                or 'ai_act_regulation'). Leave blank to search all documents.

    Returns matching text snippets with exact document titles and page citations.
    """
    results = _DOCUMENT_STORE.search(query=query, doc_id=doc_id, max_results=4)
    if not results:
        return f"No matches found for query '{query}'. Try broader terms or check list_eu_documents."

    output = [f"Found {len(results)} relevant excerpt(s) across EU AI Act documents:"]
    for i, res in enumerate(results, start=1):
        secs = f" [Sections: {', '.join(res['sections'][:2])}]" if res["sections"] else ""
        output.append(
            f"\n--- Match {i} ---\n"
            f"Source Document: {res['doc_title']} (ID: `{res['doc_id']}`)\n"
            f"Citation: Page {res['page_number']}{secs}\n"
            f"Excerpt: {res['snippet']}\n"
        )
    return "\n".join(output)


@tool
def read_eu_article_or_section(doc_id: str, section_name: str) -> str:
    """Retrieve the verbatim text of an article or section from an EU AI Act document.

    Args:
        doc_id: The document identifier (e.g. 'prohibited_practices', 'ai_act_regulation', 'definition_guidelines').
        section_name: The name of the article or section (e.g. 'Article 5', 'Article 3', 'Section 2').

    Returns the extracted text and official page citation.
    """
    res = _DOCUMENT_STORE.read_section(doc_id=doc_id, section_name=section_name)
    if not res.get("found"):
        return f"Could not retrieve section: {res.get('error')}"

    return (
        f"Official Citation: {res['doc_title']}, Page {res['primary_page']}\n"
        f"Section: {res['section_name']}\n"
        f"Verbatim Content:\n{res['content']}"
    )
