"""
ai_engine.agents.tools
~~~~~~~~~~~~~~~~~~~~~~
LangChain StructuredTool definitions for SYNAPSE ReAct agents.

Phase 5.1 — Agent Framework (Week 13)

Tools implemented:
  1. search_knowledge_base  — semantic search across pgvector collections
  2. fetch_articles         — retrieve articles from the SYNAPSE database
  3. analyze_trends         — technology trend analysis from stored data
  4. search_github          — GitHub trending repos via REST API
  5. fetch_arxiv_papers     — arXiv paper search via public API

Each tool:
  - Has a Pydantic input schema (StructuredTool)
  - Returns a plain string (agent-readable)
  - Has a 30-second timeout on external calls
  - Handles errors gracefully (returns error string, never raises)
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared HTTP timeout (seconds)
# ---------------------------------------------------------------------------
_HTTP_TIMEOUT = 30


# ===========================================================================
# 1. search_knowledge_base
# ===========================================================================


class SearchKnowledgeBaseInput(BaseModel):
    query: str = Field(..., description="Natural language search query")
    limit: int = Field(
        default=10, ge=1, le=50, description="Maximum number of results to return"
    )
    content_types: Optional[List[str]] = Field(
        default=None,
        description="Filter by content type: articles, papers, repositories, videos. Defaults to all.",
    )
    min_score: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Minimum similarity score (0–1)"
    )


def _search_knowledge_base(
    query: str,
    limit: int = 10,
    content_types: Optional[List[str]] = None,
    min_score: float = 0.0,
) -> str:
    """Execute semantic search against the pgvector knowledge base."""
    try:
        from ai_engine.rag.retriever import SynapseRetriever

        retriever = SynapseRetriever(
            k=limit,
            score_threshold=min_score,
            content_types=content_types
            or ["articles", "papers", "repositories", "videos"],
        )
        docs = retriever.invoke(query)

        if not docs:
            return f"No results found for query: '{query}'"

        results = []
        for i, doc in enumerate(docs[:limit], 1):
            meta = doc.metadata
            title = meta.get("title") or meta.get("name") or "Untitled"
            url = meta.get("source") or meta.get("url") or ""
            ctype = meta.get("content_type", "document")
            score = meta.get("similarity_score", "N/A")
            snippet = doc.page_content[:300].strip()
            results.append(
                f"{i}. [{ctype.upper()}] {title}\n"
                f"   Score: {score}\n"
                f"   URL: {url}\n"
                f"   Snippet: {snippet}"
            )

        return f"Found {len(results)} results for '{query}':\n\n" + "\n\n".join(results)

    except Exception as exc:
        logger.error("search_knowledge_base failed: %s", exc)
        return f"Search failed: {exc}"


def make_search_knowledge_base_tool() -> StructuredTool:
    return StructuredTool.from_function(
        func=_search_knowledge_base,
        name="search_knowledge_base",
        description=(
            "Search the SYNAPSE knowledge base using semantic similarity. "
            "Use this tool to find relevant articles, research papers, GitHub repositories, "
            "or videos. Supports optional content type filtering and minimum relevance score."
        ),
        args_schema=SearchKnowledgeBaseInput,
        return_direct=False,
    )


# ===========================================================================
# 2. fetch_articles
# ===========================================================================


class FetchArticlesInput(BaseModel):
    topic: str = Field(..., description="Topic or keyword to search for in articles")
    days_back: int = Field(
        default=7, ge=1, le=365, description="How many days back to search"
    )
    limit: int = Field(
        default=20, ge=1, le=100, description="Maximum articles to return"
    )
    source: Optional[str] = Field(
        default=None,
        description="Filter by source name, e.g. 'hackernews', 'arxiv', 'github'",
    )


def _fetch_articles(
    topic: str,
    days_back: int = 7,
    limit: int = 20,
    source: Optional[str] = None,
) -> str:
    """Fetch articles from the SYNAPSE PostgreSQL database."""
    try:
        import django

        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")
        try:
            django.setup()
        except RuntimeError:
            pass  # already set up

        from apps.articles.models import Article

        from django.utils import timezone

        cutoff = timezone.now() - timedelta(days=days_back)
        qs = (
            Article.objects.filter(
                scraped_at__gte=cutoff,
            )
            .select_related("source")
            .order_by("-trending_score", "-scraped_at")
        )

        if topic:
            from django.db.models import Q

            qs = qs.filter(
                Q(title__icontains=topic)
                | Q(summary__icontains=topic)
                | Q(topic__icontains=topic)
                | Q(keywords__icontains=topic)
            )

        if source:
            qs = qs.filter(source__icontains=source)

        articles = qs[:limit]

        if not articles.exists():
            return (
                f"No articles found for topic '{topic}' in the last {days_back} days."
            )

        results = []
        for i, a in enumerate(articles, 1):
            results.append(
                f"{i}. {a.title}\n"
                f"   Source: {a.source} | Topic: {a.topic} | Sentiment: {a.sentiment_score}\n"
                f"   Published: {(a.published_at or a.scraped_at).strftime('%Y-%m-%d')}\n"
                f"   URL: {a.url}\n"
                f"   Summary: {(a.summary or a.content[:200]).strip()[:300]}"
            )

        return (
            f"Found {len(results)} articles for '{topic}' (last {days_back} days):\n\n"
            + "\n\n".join(results)
        )

    except Exception as exc:
        logger.error("fetch_articles failed: %s", exc)
        return f"Failed to fetch articles: {exc}"


def make_fetch_articles_tool() -> StructuredTool:
    return StructuredTool.from_function(
        func=_fetch_articles,
        name="fetch_articles",
        description=(
            "Retrieve articles from the SYNAPSE database filtered by topic and date range. "
            "Use this to get the latest news and articles on a specific technology, framework, "
            "or domain. Optionally filter by source (hackernews, arxiv, etc.)."
        ),
        args_schema=FetchArticlesInput,
        return_direct=False,
    )


# ===========================================================================
# 3. analyze_trends
# ===========================================================================


class AnalyzeTrendsInput(BaseModel):
    technologies: List[str] = Field(
        ...,
        description="List of technology names to analyze, e.g. ['Python', 'Rust', 'LLM']",
    )
    period_days: int = Field(
        default=30,
        ge=1,
        le=365,
        description="Analysis period in days",
    )


def _analyze_trends(
    technologies: List[str],
    period_days: int = 30,
) -> str:
    """Analyze technology trends from SYNAPSE database article and repository data."""
    try:
        import django

        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")
        try:
            django.setup()
        except RuntimeError:
            pass

        from apps.articles.models import Article
        from apps.repositories.models import Repository

        from django.db.models import Avg, Count, Q
        from django.utils import timezone

        cutoff = timezone.now() - timedelta(days=period_days)
        report_lines = [
            f"Technology Trend Analysis — last {period_days} days\n" f"{'=' * 50}"
        ]

        for tech in technologies:
            tech_q = (
                Q(title__icontains=tech)
                | Q(keywords__icontains=tech)
                | Q(topic__icontains=tech)
            )

            # Articles
            article_count = Article.objects.filter(
                tech_q, scraped_at__gte=cutoff
            ).count()
            avg_sentiment = (
                Article.objects.filter(tech_q, scraped_at__gte=cutoff).aggregate(
                    avg=Avg("sentiment_score")
                )["avg"]
            ) or 0.0

            # Repositories
            repo_q = (
                Q(name__icontains=tech)
                | Q(description__icontains=tech)
                | Q(topics__icontains=tech)
            )
            repo_count = Repository.objects.filter(
                repo_q, scraped_at__gte=cutoff
            ).count()
            top_repos = (
                Repository.objects.filter(repo_q)
                .order_by("-stars")[:3]
                .values_list("name", "stars")
            )
            top_repos_str = (
                ", ".join(f"{n} (★{s})" for n, s in top_repos) or "None found"
            )

            sentiment_label = (
                "Positive 📈"
                if avg_sentiment > 0.1
                else "Negative 📉" if avg_sentiment < -0.1 else "Neutral ➡️"
            )

            report_lines.append(
                f"\n🔍 {tech}\n"
                f"   Articles:    {article_count}\n"
                f"   Repositories:{repo_count}\n"
                f"   Sentiment:   {sentiment_label} ({avg_sentiment:.3f})\n"
                f"   Top Repos:   {top_repos_str}"
            )

        return "\n".join(report_lines)

    except Exception as exc:
        logger.error("analyze_trends failed: %s", exc)
        return f"Trend analysis failed: {exc}"


def make_analyze_trends_tool() -> StructuredTool:
    return StructuredTool.from_function(
        func=_analyze_trends,
        name="analyze_trends",
        description=(
            "Analyze technology trends over a specified time period using SYNAPSE data. "
            "Returns article counts, repository counts, and sentiment scores for each technology. "
            "Great for identifying which technologies are gaining or losing traction."
        ),
        args_schema=AnalyzeTrendsInput,
        return_direct=False,
    )


# ===========================================================================
# 4. search_github
# ===========================================================================


class SearchGitHubInput(BaseModel):
    query: str = Field(..., description="Search query for GitHub repositories")
    language: Optional[str] = Field(
        default=None,
        description="Filter by programming language, e.g. 'Python', 'TypeScript'",
    )
    stars_min: int = Field(default=100, ge=0, description="Minimum number of stars")
    limit: int = Field(
        default=10, ge=1, le=30, description="Maximum repositories to return"
    )
    sort: str = Field(
        default="stars", description="Sort by: stars, forks, updated, best-match"
    )


def _search_github(
    query: str,
    language: Optional[str] = None,
    stars_min: int = 100,
    limit: int = 10,
    sort: str = "stars",
) -> str:
    """Search GitHub repositories via the REST API v3."""
    try:
        github_token = os.environ.get("GITHUB_TOKEN", "")
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "SYNAPSE-Agent/1.0",
        }
        if github_token:
            headers["Authorization"] = f"token {github_token}"

        # Build query string
        q = query
        if language:
            q += f" language:{language}"
        if stars_min > 0:
            q += f" stars:>={stars_min}"

        params = {
            "q": q,
            "sort": sort,
            "order": "desc",
            "per_page": min(limit, 30),
        }

        with httpx.Client(timeout=_HTTP_TIMEOUT) as client:
            resp = client.get(
                "https://api.github.com/search/repositories",
                params=params,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()

        items = data.get("items", [])
        total = data.get("total_count", 0)

        if not items:
            return f"No GitHub repositories found for query: '{query}'"

        results = []
        for i, repo in enumerate(items[:limit], 1):
            results.append(
                f"{i}. {repo['full_name']} (★{repo['stargazers_count']:,})\n"
                f"   Language: {repo.get('language') or 'N/A'} | Forks: {repo['forks_count']:,}\n"
                f"   URL: {repo['html_url']}\n"
                f"   Description: {(repo.get('description') or 'No description')[:200]}\n"
                f"   Updated: {repo['updated_at'][:10]}"
            )

        return (
            f"GitHub search for '{query}' — {total:,} total results, showing top {len(results)}:\n\n"
            + "\n\n".join(results)
        )

    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 403:
            return "GitHub API rate limit reached. Please set GITHUB_TOKEN environment variable."
        return f"GitHub API error {exc.response.status_code}: {exc}"
    except Exception as exc:
        logger.error("search_github failed: %s", exc)
        return f"GitHub search failed: {exc}"


def make_search_github_tool() -> StructuredTool:
    return StructuredTool.from_function(
        func=_search_github,
        name="search_github",
        description=(
            "Search GitHub for repositories matching a query. "
            "Filter by programming language and minimum star count. "
            "Use this to discover trending projects, libraries, or frameworks on GitHub."
        ),
        args_schema=SearchGitHubInput,
        return_direct=False,
    )


# ===========================================================================
# 5. fetch_arxiv_papers
# ===========================================================================


class FetchArxivPapersInput(BaseModel):
    query: str = Field(
        ..., description="Search query for arXiv papers (title, abstract, or keyword)"
    )
    max_results: int = Field(
        default=10, ge=1, le=50, description="Maximum papers to return"
    )
    categories: Optional[List[str]] = Field(
        default=None,
        description="arXiv category filters, e.g. ['cs.AI', 'cs.LG', 'stat.ML']",
    )
    sort_by: str = Field(
        default="relevance",
        description="Sort order: relevance, lastUpdatedDate, submittedDate",
    )


def _fetch_arxiv_papers(
    query: str,
    max_results: int = 10,
    categories: Optional[List[str]] = None,
    sort_by: str = "relevance",
) -> str:
    """Fetch research papers from arXiv via the public Atom API."""
    try:
        # Build search query
        search_query = query
        if categories:
            cat_filter = " OR ".join(f"cat:{c}" for c in categories)
            search_query = f"({query}) AND ({cat_filter})"

        params = {
            "search_query": f"all:{search_query}",
            "max_results": max_results,
            "sortBy": sort_by,
            "sortOrder": "descending",
        }

        with httpx.Client(timeout=_HTTP_TIMEOUT) as client:
            resp = client.get("https://export.arxiv.org/api/query", params=params)
            resp.raise_for_status()
            content = resp.text

        # Parse Atom XML
        import xml.etree.ElementTree as ET

        ns = {"atom": "http://www.w3.org/2005/Atom"}
        root = ET.fromstring(content)
        entries = root.findall("atom:entry", ns)

        if not entries:
            return f"No arXiv papers found for query: '{query}'"

        results = []
        for i, entry in enumerate(entries[:max_results], 1):
            title_el = entry.find("atom:title", ns)
            summary_el = entry.find("atom:summary", ns)
            published_el = entry.find("atom:published", ns)
            id_el = entry.find("atom:id", ns)
            authors = entry.findall("atom:author", ns)

            title = (title_el.text or "").strip().replace("\n", " ")
            summary = (summary_el.text or "").strip().replace("\n", " ")[:300]
            published = (published_el.text or "")[:10]
            paper_id = (id_el.text or "").strip()
            author_names = [(a.find("atom:name", ns).text or "") for a in authors[:3]]
            author_str = ", ".join(author_names)
            if len(authors) > 3:
                author_str += f" et al. (+{len(authors) - 3})"

            categories_els = entry.findall("atom:category", ns)
            cats = [c.attrib.get("term", "") for c in categories_els[:3]]

            results.append(
                f"{i}. {title}\n"
                f"   Authors: {author_str}\n"
                f"   Categories: {', '.join(cats)}\n"
                f"   Published: {published}\n"
                f"   URL: {paper_id}\n"
                f"   Abstract: {summary}..."
            )

        return (
            f"arXiv papers for '{query}' — showing {len(results)} results:\n\n"
            + "\n\n".join(results)
        )

    except Exception as exc:
        logger.error("fetch_arxiv_papers failed: %s", exc)
        return f"arXiv fetch failed: {exc}"


def make_fetch_arxiv_papers_tool() -> StructuredTool:
    return StructuredTool.from_function(
        func=_fetch_arxiv_papers,
        name="fetch_arxiv_papers",
        description=(
            "Search and fetch research papers from arXiv using the public API. "
            "Filter by category (e.g. cs.AI, cs.LG) and sort by relevance or date. "
            "Use this for academic research, literature reviews, or finding the latest AI/ML papers."
        ),
        args_schema=FetchArxivPapersInput,
        return_direct=False,
    )


# ════════════════════════════════════════════════════════════════════════════
# TASK-303-B1 — Tavily Web Search
# ════════════════════════════════════════════════════════════════════════════


class WebSearchInput(BaseModel):
    query: str = Field(..., description="Web search query")
    max_results: int = Field(
        default=5,
        description="Number of results to return (1–10)",
        ge=1,
        le=10,
    )
    search_depth: str = Field(
        default="basic",
        description="Search depth: 'basic' (fast) or 'advanced' (thorough)",
    )
    include_domains: Optional[list[str]] = Field(
        default=None,
        description="Optional domains to restrict search to, e.g. ['arxiv.org']",
    )


def _web_search(
    query: str,
    max_results: int = 5,
    search_depth: str = "basic",
    include_domains: Optional[list[str]] = None,
) -> list[dict]:
    """Live web search via Tavily API."""
    # ERR-04: Validate key at call time — strip whitespace, check minimum length
    # os is imported at module level
    tavily_key = os.environ.get("TAVILY_API_KEY", "").strip()
    if not tavily_key or len(tavily_key) < 8:
        return [
            {
                "error": "TAVILY_API_KEY not configured or invalid. Set it in .env to enable live web search."
            }
        ]

    try:
        from tavily import TavilyClient  # type: ignore

        client = TavilyClient(api_key=tavily_key)
        kwargs: dict = {
            "query": query,
            "max_results": max_results,
            "search_depth": search_depth,
        }
        if include_domains:
            kwargs["include_domains"] = include_domains
        response = client.search(**kwargs)
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": (r.get("content", "") or "")[:400],
                "score": r.get("score", 0.0),
            }
            for r in response.get("results", [])
        ]
    except ImportError:
        return [
            {"error": "tavily-python not installed. Run: pip install tavily-python"}
        ]
    except Exception as exc:
        logger.error("web_search error: %s", exc)
        return [{"error": str(exc)}]


def make_web_search_tool() -> StructuredTool:
    return StructuredTool.from_function(
        func=_web_search,
        name="web_search",
        description=(
            "Search the live web for current information, news, documentation, or any topic "
            "not in the SYNAPSE knowledge base. Returns titles, URLs, and snippets. "
            "Use this for up-to-date information beyond the training cutoff."
        ),
        args_schema=WebSearchInput,
    )


# ════════════════════════════════════════════════════════════════════════════
# TASK-303-B2 — Python Code Execution Sandbox
# ════════════════════════════════════════════════════════════════════════════


class RunPythonInput(BaseModel):
    code: str = Field(
        ...,
        description="Python code to execute. Available: math, statistics, json, datetime, re, collections, itertools. No internet or filesystem.",
    )
    timeout_seconds: int = Field(default=10, ge=1, le=30)


_SAFE_BUILTINS_KEYS = {
    "None",
    "True",
    "False",
    "int",
    "float",
    "str",
    "bool",
    "list",
    "dict",
    "set",
    "tuple",
    "bytes",
    "len",
    "range",
    "enumerate",
    "zip",
    "map",
    "filter",
    "sorted",
    "reversed",
    "min",
    "max",
    "sum",
    "abs",
    "round",
    "print",
    "repr",
    "type",
    "isinstance",
    "issubclass",
    "hasattr",
    "callable",
    "iter",
    "next",
    "any",
    "all",
    "hash",
    "chr",
    "ord",
    "hex",
    "oct",
    "bin",
    "pow",
    "divmod",
    "format",
    "vars",
    "dir",
}
# NOTE: "getattr", "setattr", "delattr", "id", "__import__" are intentionally
# excluded — getattr/setattr can be used to escape the sandbox by accessing
# dunder attributes on objects (e.g. ().__class__.__bases__[0].__subclasses__()).

_SAFE_MODULES = {
    "math",
    "statistics",
    "json",
    "datetime",
    "re",
    "collections",
    "itertools",
    "functools",
    "string",
    "decimal",
    "fractions",
    "random",
}

# Patterns that are blocked outright before execution.
# This is a defence-in-depth measure — the primary control is the restricted
# builtins dict and safe-import guard. String matching alone is insufficient
# (e.g. getattr bypass), so we do NOT rely solely on this list.
_BLOCKED_PATTERNS = [
    # Dunder escape vectors
    "__class__",
    "__bases__",
    "__subclasses__",
    "__globals__",
    "__builtins__",
    "__import__",
    "__loader__",
    "__spec__",
    "__code__",
    "__func__",
    "__self__",
    "__mro__",
    # Dangerous stdlib modules
    "importlib",
    "subprocess",
    "multiprocessing",
    "socket",
    "requests",
    "urllib",
    "httpx",
    "aiohttp",
    "shutil",
    "pathlib",
    "tempfile",
    # File / OS access
    "open(",
    "os.system",
    "os.popen",
    "os.exec",
    "os.spawn",
    "os.fork",
    "os.path",
    # Code execution
    "eval(",
    "exec(",
    "compile(",
    # Reflection / introspection abuse
    "builtins",
    "ctypes",
    "cffi",
]


def _run_python_code(code: str, timeout_seconds: int = 10) -> dict:
    """Execute Python code in a restricted sandbox.

    Security model (defence in depth):
    1. Blocked-pattern scan — fast pre-flight check for known escape vectors.
    2. Restricted builtins dict — only explicitly whitelisted builtins are
       injected; `getattr`, `setattr`, `__import__` etc. are excluded.
    3. Safe-import guard — replaces `__import__` with a function that only
       allows modules in `_SAFE_MODULES`.
    4. Thread timeout — kills runaway code after `timeout_seconds`.

    Limitations: `exec()` sandboxing in CPython is not a security boundary.
    Do NOT use this to run untrusted code from unauthenticated sources.
    For stronger isolation, use Docker-based sandboxing (e.g. gVisor).
    """
    import io
    import sys
    import threading
    import traceback

    # 1. Pre-flight blocked-pattern scan
    for pattern in _BLOCKED_PATTERNS:
        if pattern in code:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"SecurityError: '{pattern}' is not allowed in the sandbox.",
                "result": None,
            }

    # 2. Cap code size to prevent memory exhaustion
    if len(code) > 50_000:
        return {
            "success": False,
            "stdout": "",
            "stderr": "SecurityError: Code exceeds maximum allowed size (50,000 characters).",
            "result": None,
        }

    stdout_buf = io.StringIO()
    err_container: dict = {}

    def _execute():
        # 3. Build restricted builtins — only whitelisted keys
        import builtins as _builtins_module

        safe_builtins = {
            k: getattr(_builtins_module, k)
            for k in _SAFE_BUILTINS_KEYS
            if hasattr(_builtins_module, k)
        }

        def _safe_import(name, *args, fromlist=(), level=0, **kwargs):
            # Strip submodule path — e.g. "os.path" → block at "os"
            top_level = name.split(".")[0]
            if top_level in _SAFE_MODULES:
                import importlib

                return importlib.import_module(name)
            raise ImportError(f"Module '{name}' is not allowed in the sandbox.")

        safe_builtins["__import__"] = _safe_import

        # Completely isolated global namespace — no access to host globals
        sandbox_globals: dict = {
            "__builtins__": safe_builtins,
            "__name__": "__sandbox__",
            "__doc__": None,
        }

        old_stdout = sys.stdout
        sys.stdout = stdout_buf
        try:
            exec(compile(code, "<sandbox>", "exec"), sandbox_globals)  # noqa: S102
        except Exception:
            err_container["error"] = traceback.format_exc()
        finally:
            sys.stdout = old_stdout

    t = threading.Thread(target=_execute, daemon=True)
    t.start()
    t.join(timeout=timeout_seconds)

    if t.is_alive():
        return {
            "success": False,
            "stdout": stdout_buf.getvalue(),
            "stderr": f"TimeoutError: Code execution exceeded {timeout_seconds}s limit.",
            "result": None,
        }

    error = err_container.get("error")
    return {
        "success": error is None,
        "stdout": stdout_buf.getvalue()[:4000],
        "stderr": (error or "")[:2000],
        "result": None,
    }


def make_run_python_tool() -> StructuredTool:
    return StructuredTool.from_function(
        func=_run_python_code,
        name="run_python_code",
        description=(
            "Execute Python code in a safe sandbox for calculations, data analysis, "
            "string manipulation, statistics, JSON processing, and date arithmetic. "
            "Available modules: math, statistics, json, datetime, re, collections, itertools. "
            "No internet or file system access. Returns stdout and any errors."
        ),
        args_schema=RunPythonInput,
    )


# ════════════════════════════════════════════════════════════════════════════
# TASK-303-B3 — PDF / Document Reader
# ════════════════════════════════════════════════════════════════════════════


class ReadDocumentInput(BaseModel):
    url: str = Field(..., description="Public URL of a PDF or plain-text document.")
    max_chars: int = Field(default=8000, ge=1000, le=20000)


# SEC-07: Maximum download size for _read_document — prevents a malicious URL
# from causing the agent to download a multi-GB file into memory.
_MAX_DOWNLOAD_BYTES = int(os.environ.get("AGENT_MAX_DOWNLOAD_MB", "20")) * 1024 * 1024


def _read_document(url: str, max_chars: int = 8000) -> dict:
    """Download and extract text from a public PDF or document URL.

    SEC-07: Enforces a maximum download size (_MAX_DOWNLOAD_BYTES) to prevent
    memory exhaustion from large files served by malicious or misbehaving URLs.
    """
    import re
    import tempfile

    if not url.startswith(("http://", "https://")):
        return {"error": "Only http:// and https:// URLs are supported."}

    tmp_path: str | None = None
    try:
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            # Stream the response to check Content-Length before downloading fully
            with client.stream(
                "GET", url, headers={"User-Agent": "SYNAPSE-Agent/1.0"}
            ) as resp:
                resp.raise_for_status()
                content_type = resp.headers.get("content-type", "").lower()

                # Check Content-Length header first (not always present)
                content_length = int(resp.headers.get("content-length", 0))
                if content_length > _MAX_DOWNLOAD_BYTES:
                    return {
                        "error": f"File too large: {content_length / 1024 / 1024:.1f} MB "
                        f"(limit: {_MAX_DOWNLOAD_BYTES // 1024 // 1024} MB)"
                    }

                # Stream body with running size check
                chunks = []
                downloaded = 0
                for chunk in resp.iter_bytes(chunk_size=65536):
                    downloaded += len(chunk)
                    if downloaded > _MAX_DOWNLOAD_BYTES:
                        return {
                            "error": f"File too large: exceeded "
                            f"{_MAX_DOWNLOAD_BYTES // 1024 // 1024} MB download limit."
                        }
                    chunks.append(chunk)
                raw_bytes = b"".join(chunks)
    except Exception as exc:
        return {"error": f"Failed to fetch document: {exc}"}

    if "pdf" in content_type or url.lower().endswith(".pdf"):
        try:
            import fitz  # type: ignore

            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(raw_bytes)
                tmp_path = tmp.name
            try:
                doc = fitz.open(tmp_path)
                pages = [p.get_text() for p in doc]
                doc.close()
            finally:
                # Always clean up temp file — even if fitz.open() raises
                if tmp_path and os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                    tmp_path = None
            text = "\n".join(pages)
            doc_type, page_count = "pdf", len(pages)
        except ImportError:
            return {"error": "pymupdf not installed. Run: pip install pymupdf"}
        except Exception as exc:
            return {"error": f"PDF extraction failed: {exc}"}
    else:
        text = raw_bytes.decode("utf-8", errors="replace")
        doc_type = "html" if "html" in content_type else "text"
        page_count = None
        if "html" in content_type:
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text).strip()

    truncated = len(text) > max_chars
    return {
        "url": url,
        "doc_type": doc_type,
        "page_count": page_count,
        "char_count": len(text),
        "truncated": truncated,
        "text": text[:max_chars],
    }


def make_read_document_tool() -> StructuredTool:
    return StructuredTool.from_function(
        func=_read_document,
        name="read_document",
        description=(
            "Download and extract text from a public PDF or document URL. "
            "Use for reading research papers, reports, or documentation. "
            "Returns extracted text with page count and metadata."
        ),
        args_schema=ReadDocumentInput,
    )


# ════════════════════════════════════════════════════════════════════════════
# TASK-303-B4 — Chart / Visualization Generator
# ════════════════════════════════════════════════════════════════════════════


class GenerateChartInput(BaseModel):
    chart_type: str = Field(
        ..., description="Chart type: 'bar', 'line', 'pie', 'scatter', 'histogram'"
    )
    title: str = Field(default="", description="Chart title")
    labels: list[str] = Field(..., description="X-axis or pie slice labels")
    values: list[float] = Field(..., description="Corresponding numeric values")
    x_label: str = Field(default="", description="X-axis label")
    y_label: str = Field(default="", description="Y-axis label")
    color: str = Field(default="#6366f1", description="Primary color as hex string")


def _generate_chart(
    chart_type: str,
    labels: list[str],
    values: list[float],
    title: str = "",
    x_label: str = "",
    y_label: str = "",
    color: str = "#6366f1",
) -> dict:
    """Generate a chart as base64-encoded PNG."""
    import base64
    import io

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return {"error": "matplotlib not installed. Run: pip install matplotlib"}

    if not labels:
        return {"error": "labels must be non-empty."}
    if chart_type != "histogram" and len(labels) != len(values):
        return {"error": "labels and values must have the same length."}

    plt.rcParams.update(
        {
            "figure.facecolor": "#0f172a",
            "axes.facecolor": "#1e293b",
            "axes.edgecolor": "#334155",
            "axes.labelcolor": "#94a3b8",
            "xtick.color": "#94a3b8",
            "ytick.color": "#94a3b8",
            "text.color": "#e2e8f0",
            "grid.color": "#334155",
            "grid.alpha": 0.5,
        }
    )

    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=120)
    ct = chart_type.lower().strip()

    try:
        if ct == "bar":
            bars = ax.bar(
                labels, values, color=color, edgecolor="#334155", linewidth=0.5
            )
            ax.bar_label(bars, fmt="%.1f", color="#94a3b8", fontsize=8, padding=3)
            ax.grid(axis="y", linestyle="--")
        elif ct == "line":
            ax.plot(labels, values, color=color, marker="o", linewidth=2, markersize=5)
            ax.fill_between(range(len(labels)), values, alpha=0.15, color=color)
            ax.set_xticks(range(len(labels)))
            ax.set_xticklabels(
                labels, rotation=30 if len(labels) > 6 else 0, ha="right"
            )
            ax.grid(axis="y", linestyle="--")
        elif ct == "pie":
            palette = [
                "#6366f1",
                "#06b6d4",
                "#10b981",
                "#f59e0b",
                "#ef4444",
                "#8b5cf6",
                "#ec4899",
                "#14b8a6",
            ]
            ax.pie(
                values,
                labels=labels,
                colors=palette[: len(labels)],
                autopct="%1.1f%%",
                startangle=90,
                wedgeprops={"edgecolor": "#0f172a", "linewidth": 1.5},
            )
        elif ct == "scatter":
            ax.scatter(
                labels, values, color=color, s=80, alpha=0.8, edgecolors="#334155"
            )
            ax.grid(linestyle="--")
        elif ct == "histogram":
            ax.hist(values, bins=min(len(values), 20), color=color, edgecolor="#334155")
            ax.grid(axis="y", linestyle="--")
        else:
            return {
                "error": f"Unknown chart_type '{ct}'. Use: bar, line, pie, scatter, histogram."
            }

        if title:
            ax.set_title(title, color="#e2e8f0", fontsize=13, fontweight="bold", pad=12)
        if x_label and ct != "pie":
            ax.set_xlabel(x_label, color="#94a3b8", fontsize=10)
        if y_label and ct != "pie":
            ax.set_ylabel(y_label, color="#94a3b8", fontsize=10)

        plt.tight_layout()
        buf = io.BytesIO()
        fig.savefig(
            buf, format="png", bbox_inches="tight", facecolor=fig.get_facecolor()
        )
        plt.close(fig)
        buf.seek(0)
        b64 = base64.b64encode(buf.read()).decode("utf-8")
        return {
            "success": True,
            "chart_type": ct,
            "title": title,
            "base64_png": b64,
            "data_uri": f"data:image/png;base64,{b64}",
        }
    except Exception as exc:
        plt.close("all")
        return {"error": str(exc)}


def make_generate_chart_tool() -> StructuredTool:
    return StructuredTool.from_function(
        func=_generate_chart,
        name="generate_chart",
        description=(
            "Generate a chart/visualization from data as a base64-encoded PNG. "
            "Types: bar, line, pie, scatter, histogram. "
            "Use for visualizing data, comparing values, showing trends, or plotting distributions. "
            "The returned data_uri can be embedded directly in HTML as <img src='...'/>."
        ),
        args_schema=GenerateChartInput,
    )
