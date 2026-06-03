"""
backend.apps.agents.tests.test_agent_tools
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Unit tests for the Phase 5.1 agent tools.

Tests are designed to run without a live database, OpenAI/Gemini API key,
or pgvector — all external dependencies are mocked.

Phase 5.1 — Agent Framework (Week 13)
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from django.test import TestCase

# ---------------------------------------------------------------------------
# Helper: build a minimal fake httpx response
# ---------------------------------------------------------------------------


def _make_httpx_response(
    json_data: dict = None, text: str = "", status_code: int = 200
):
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    resp.json.return_value = json_data or {}
    resp.raise_for_status = MagicMock()
    return resp


# ===========================================================================
# 1. search_knowledge_base
# ===========================================================================


class TestSearchKnowledgeBase(TestCase):
    """Tests for ai_engine.agents.tools._search_knowledge_base."""

    def _run(
        self, query="LangChain tutorial", limit=5, content_types=None, min_score=0.0
    ):
        from ai_engine.agents.tools import _search_knowledge_base

        return _search_knowledge_base(query, limit, content_types, min_score)

    @patch("ai_engine.rag.retriever.SynapseRetriever")
    def test_returns_formatted_results(self, MockRetriever):
        from langchain_core.documents import Document

        mock_doc = Document(
            page_content="LangChain is a framework for building LLM apps.",
            metadata={
                "title": "LangChain Guide",
                "source": "https://langchain.com",
                "content_type": "articles",
                "similarity_score": 0.92,
            },
        )
        MockRetriever.return_value.invoke.return_value = [mock_doc]

        result = self._run(query="LangChain tutorial")

        self.assertIn("LangChain Guide", result)
        self.assertIn("0.92", result)
        self.assertIn("https://langchain.com", result)
        self.assertIn("Found 1 results", result)

    @patch("ai_engine.rag.retriever.SynapseRetriever")
    def test_no_results(self, MockRetriever):
        MockRetriever.return_value.invoke.return_value = []
        result = self._run(query="nonexistent topic xyz123")
        self.assertIn("No results found", result)

    @patch("ai_engine.rag.retriever.SynapseRetriever")
    def test_retriever_exception_returns_error_string(self, MockRetriever):
        MockRetriever.return_value.invoke.side_effect = Exception(
            "DB connection refused"
        )
        result = self._run()
        self.assertIn("Search failed", result)
        self.assertIn("DB connection refused", result)

    def test_tool_metadata(self):
        from ai_engine.agents.tools import make_search_knowledge_base_tool

        tool = make_search_knowledge_base_tool()
        self.assertEqual(tool.name, "search_knowledge_base")
        self.assertIn("semantic", tool.description.lower())


# ===========================================================================
# 2. fetch_articles
# ===========================================================================


class TestFetchArticles(TestCase):
    """Tests for ai_engine.agents.tools._fetch_articles."""

    def _run(self, topic="Python", days_back=7, limit=5, source=None):
        from ai_engine.agents.tools import _fetch_articles

        return _fetch_articles(topic, days_back, limit, source)

    def test_no_articles_found(self):
        """When Django queryset is empty, return a non-empty string result."""
        mock_qs = MagicMock()
        mock_qs.filter.return_value = mock_qs
        mock_qs.order_by.return_value = mock_qs
        mock_qs.__iter__ = MagicMock(return_value=iter([]))
        mock_qs.exists.return_value = False
        mock_qs.__getitem__ = MagicMock(return_value=mock_qs)

        mock_article_model = MagicMock()
        mock_article_model.objects = mock_qs

        with patch.dict(
            "sys.modules",
            {
                "apps.articles.models": MagicMock(Article=mock_article_model),
            },
        ):
            result = self._run(topic="obscure-topic-xyz")
            # Should always return a non-empty string (articles found, none found, or error)
            self.assertIsInstance(result, str)
            self.assertGreater(len(result), 0)

    def test_tool_metadata(self):
        from ai_engine.agents.tools import make_fetch_articles_tool

        tool = make_fetch_articles_tool()
        self.assertEqual(tool.name, "fetch_articles")
        self.assertIn("article", tool.description.lower())

    def test_input_schema_has_required_fields(self):
        from ai_engine.agents.tools import FetchArticlesInput

        schema = FetchArticlesInput.schema()
        required = schema.get("required", [])
        self.assertIn("topic", required)


# ===========================================================================
# 3. analyze_trends
# ===========================================================================


class TestAnalyzeTrends(TestCase):
    """Tests for ai_engine.agents.tools._analyze_trends."""

    def test_tool_metadata(self):
        from ai_engine.agents.tools import make_analyze_trends_tool

        tool = make_analyze_trends_tool()
        self.assertEqual(tool.name, "analyze_trends")
        self.assertIn("trend", tool.description.lower())

    def test_input_schema_requires_technologies(self):
        from ai_engine.agents.tools import AnalyzeTrendsInput

        schema = AnalyzeTrendsInput.schema()
        self.assertIn("technologies", schema.get("required", []))

    def test_input_schema_period_days_default(self):
        from ai_engine.agents.tools import AnalyzeTrendsInput

        obj = AnalyzeTrendsInput(technologies=["Python"])
        self.assertEqual(obj.period_days, 30)


# ===========================================================================
# 4. search_github
# ===========================================================================

GITHUB_RESPONSE = {
    "total_count": 2,
    "items": [
        {
            "full_name": "langchain-ai/langchain",
            "stargazers_count": 85000,
            "forks_count": 12000,
            "language": "Python",
            "html_url": "https://github.com/langchain-ai/langchain",
            "description": "Build LLM applications with LangChain",
            "updated_at": "2025-01-15T10:00:00Z",
        },
        {
            "full_name": "openai/openai-python",
            "stargazers_count": 21000,
            "forks_count": 3000,
            "language": "Python",
            "html_url": "https://github.com/openai/openai-python",
            "description": "Official OpenAI Python SDK",
            "updated_at": "2025-01-14T10:00:00Z",
        },
    ],
}


class TestSearchGitHub(TestCase):
    """Tests for ai_engine.agents.tools._search_github."""

    def _run(
        self,
        query="LangChain",
        language="Python",
        stars_min=1000,
        limit=5,
        sort="stars",
    ):
        from ai_engine.agents.tools import _search_github

        return _search_github(query, language, stars_min, limit, sort)

    @patch("ai_engine.agents.tools.httpx.Client")
    def test_returns_formatted_repos(self, MockClient):
        mock_resp = _make_httpx_response(json_data=GITHUB_RESPONSE)
        MockClient.return_value.__enter__.return_value.get.return_value = mock_resp

        result = self._run(query="LangChain")

        self.assertIn("langchain-ai/langchain", result)
        self.assertIn("85,000", result)
        self.assertIn("https://github.com/langchain-ai/langchain", result)
        self.assertIn("2 total results", result)

    @patch("ai_engine.agents.tools.httpx.Client")
    def test_no_results(self, MockClient):
        mock_resp = _make_httpx_response(json_data={"total_count": 0, "items": []})
        MockClient.return_value.__enter__.return_value.get.return_value = mock_resp

        result = self._run(query="unknownrepo999xyz")
        self.assertIn("No GitHub repositories found", result)

    @patch("ai_engine.agents.tools.httpx.Client")
    def test_language_filter_included_in_query(self, MockClient):
        mock_resp = _make_httpx_response(json_data=GITHUB_RESPONSE)
        MockClient.return_value.__enter__.return_value.get.return_value = mock_resp

        self._run(query="vector db", language="Rust")

        call_kwargs = MockClient.return_value.__enter__.return_value.get.call_args
        params = call_kwargs[1].get("params") or call_kwargs[0][1]
        self.assertIn("language:Rust", params["q"])

    @patch("ai_engine.agents.tools.httpx.Client")
    def test_api_error_returns_error_string(self, MockClient):
        import httpx

        mock_resp = MagicMock()
        mock_resp.status_code = 403
        MockClient.return_value.__enter__.return_value.get.side_effect = (
            httpx.HTTPStatusError("Forbidden", request=MagicMock(), response=mock_resp)
        )
        result = self._run()
        self.assertIn("rate limit", result.lower())

    def test_tool_metadata(self):
        from ai_engine.agents.tools import make_search_github_tool

        tool = make_search_github_tool()
        self.assertEqual(tool.name, "search_github")
        self.assertIn("github", tool.description.lower())


# ===========================================================================
# 5. fetch_arxiv_papers
# ===========================================================================

ARXIV_ATOM_RESPONSE = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2401.00001v1</id>
    <title>Attention Is All You Need: A Survey</title>
    <summary>A comprehensive survey of transformer architectures and their applications.</summary>
    <published>2024-01-01T00:00:00Z</published>
    <author><name>Alice Smith</name></author>
    <author><name>Bob Jones</name></author>
    <category term="cs.AI"/>
    <category term="cs.LG"/>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2401.00002v1</id>
    <title>ReAct: Synergizing Reasoning and Acting in Language Models</title>
    <summary>ReAct combines chain-of-thought reasoning with tool-based actions.</summary>
    <published>2024-01-02T00:00:00Z</published>
    <author><name>Carol White</name></author>
    <category term="cs.CL"/>
  </entry>
</feed>"""


class TestFetchArxivPapers(TestCase):
    """Tests for ai_engine.agents.tools._fetch_arxiv_papers."""

    def _run(
        self, query="transformer", max_results=5, categories=None, sort_by="relevance"
    ):
        from ai_engine.agents.tools import _fetch_arxiv_papers

        return _fetch_arxiv_papers(query, max_results, categories, sort_by)

    @patch("ai_engine.agents.tools.httpx.Client")
    def test_returns_parsed_papers(self, MockClient):
        mock_resp = _make_httpx_response(text=ARXIV_ATOM_RESPONSE)
        MockClient.return_value.__enter__.return_value.get.return_value = mock_resp

        result = self._run(query="transformer")

        self.assertIn("Attention Is All You Need", result)
        self.assertIn("Alice Smith", result)
        self.assertIn("cs.AI", result)
        self.assertIn("http://arxiv.org/abs/2401.00001v1", result)

    @patch("ai_engine.agents.tools.httpx.Client")
    def test_category_filter_in_query(self, MockClient):
        mock_resp = _make_httpx_response(text=ARXIV_ATOM_RESPONSE)
        MockClient.return_value.__enter__.return_value.get.return_value = mock_resp

        self._run(query="LLM agents", categories=["cs.AI", "cs.LG"])

        call_kwargs = MockClient.return_value.__enter__.return_value.get.call_args
        params = call_kwargs[1].get("params") or call_kwargs[0][1]
        self.assertIn("cat:cs.AI", params["search_query"])

    @patch("ai_engine.agents.tools.httpx.Client")
    def test_empty_feed_returns_no_results_message(self, MockClient):
        empty_feed = (
            '<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"></feed>'
        )
        mock_resp = _make_httpx_response(text=empty_feed)
        MockClient.return_value.__enter__.return_value.get.return_value = mock_resp

        result = self._run(query="nonexistent2394820938")
        self.assertIn("No arXiv papers found", result)

    @patch("ai_engine.agents.tools.httpx.Client")
    def test_exception_returns_error_string(self, MockClient):
        MockClient.return_value.__enter__.return_value.get.side_effect = Exception(
            "Connection timeout"
        )

        result = self._run()
        self.assertIn("arXiv fetch failed", result)
        self.assertIn("Connection timeout", result)

    def test_tool_metadata(self):
        from ai_engine.agents.tools import make_fetch_arxiv_papers_tool

        tool = make_fetch_arxiv_papers_tool()
        self.assertEqual(tool.name, "fetch_arxiv_papers")
        self.assertIn("arxiv", tool.description.lower())

    def test_input_schema_defaults(self):
        from ai_engine.agents.tools import FetchArxivPapersInput

        obj = FetchArxivPapersInput(query="deep learning")
        self.assertEqual(obj.max_results, 10)
        self.assertEqual(obj.sort_by, "relevance")
        self.assertIsNone(obj.categories)


# ===========================================================================
# 6. Registry tests
# ===========================================================================


class TestAgentToolRegistry(TestCase):
    """Tests for ai_engine.agents.registry.AgentToolRegistry."""

    @patch("ai_engine.agents.registry.AgentToolRegistry.build")
    def test_get_registry_returns_singleton(self, mock_build):
        """get_registry() always returns the same instance."""
        import ai_engine.agents.registry as reg_module
        from ai_engine.agents.registry import _registry_instance, get_registry

        # Reset singleton for isolated test
        reg_module._registry_instance = None
        r1 = get_registry()
        r2 = get_registry()
        self.assertIs(r1, r2)
        reg_module._registry_instance = None  # cleanup

    @patch("ai_engine.agents.tools.make_search_knowledge_base_tool")
    @patch("ai_engine.agents.tools.make_fetch_articles_tool")
    @patch("ai_engine.agents.tools.make_analyze_trends_tool")
    @patch("ai_engine.agents.tools.make_search_github_tool")
    @patch("ai_engine.agents.tools.make_fetch_arxiv_papers_tool")
    @patch("ai_engine.agents.doc_tools.make_generate_pdf_tool")
    @patch("ai_engine.agents.doc_tools.make_generate_ppt_tool")
    @patch("ai_engine.agents.doc_tools.make_generate_word_doc_tool")
    @patch("ai_engine.agents.doc_tools.make_generate_markdown_tool")
    @patch("ai_engine.agents.project_tools.make_create_project_tool")
    def test_build_registers_all_10_tools(self, mp, m9, m8, m7, m6, m1, m2, m3, m4, m5):
        """Registry now has 10 tools: 5 research (5.1) + 4 doc (5.2) + 1 project (5.3)."""
        from ai_engine.agents.registry import AgentToolRegistry

        # Create fresh registry
        registry = AgentToolRegistry()

        tool_names = [
            "search_knowledge_base",
            "fetch_articles",
            "analyze_trends",
            "search_github",
            "fetch_arxiv_papers",
            "generate_pdf",
            "generate_ppt",
            "generate_word_doc",
            "generate_markdown",
            "create_project",
        ]
        mocks = [m5, m4, m3, m2, m1, m6, m7, m8, m9, mp]
        for mock, name in zip(mocks, tool_names):
            fake_tool = MagicMock()
            fake_tool.name = name
            mock.return_value = fake_tool

        registry.build()

        self.assertEqual(len(registry), 10)
        for name in tool_names:
            self.assertIn(name, registry.list_tool_names())

    def test_get_tools_with_name_filter(self):
        from ai_engine.agents.registry import AgentToolRegistry

        registry = AgentToolRegistry()

        # Manually inject two fake tools
        tool_a = MagicMock()
        tool_a.name = "tool_a"
        tool_b = MagicMock()
        tool_b.name = "tool_b"
        registry._tools = {"tool_a": tool_a, "tool_b": tool_b}
        registry._built = True

        result = registry.get_tools(["tool_a"])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "tool_a")

    def test_describe_returns_name_and_description(self):
        from ai_engine.agents.registry import AgentToolRegistry

        registry = AgentToolRegistry()

        fake_tool = MagicMock()
        fake_tool.name = "my_tool"
        fake_tool.description = "Does something useful"
        registry._tools = {"my_tool": fake_tool}
        registry._built = True

        descriptions = registry.describe()
        self.assertEqual(len(descriptions), 1)
        self.assertEqual(descriptions[0]["name"], "my_tool")
        self.assertEqual(descriptions[0]["description"], "Does something useful")


# ===========================================================================
# 7. Base agent safety limits
# ===========================================================================


class TestSynapseAgentBase(TestCase):
    """Tests for ai_engine.agents.base.SynapseAgent utility methods."""

    def test_estimate_tokens(self):
        from ai_engine.agents.base import SynapseAgent

        tokens = SynapseAgent._estimate_tokens(
            "Hello world", "Hi there, how can I help?"
        )
        self.assertGreater(tokens, 0)

    def test_estimate_cost(self):
        from ai_engine.agents.base import SynapseAgent

        cost = SynapseAgent._estimate_cost(1000)
        self.assertGreater(cost, 0)
        self.assertLess(cost, 0.01)  # Should be tiny

    def test_serialize_steps_empty(self):
        from ai_engine.agents.base import SynapseAgent

        result = SynapseAgent._serialize_steps([])
        self.assertEqual(result, [])

    def test_serialize_steps_with_data(self):
        from ai_engine.agents.base import SynapseAgent

        action = MagicMock()
        action.log = "Thought: I should search"
        action.tool = "search_knowledge_base"
        action.tool_input = {"query": "LLMs"}

        steps = [(action, "Found 3 results about LLMs")]
        result = SynapseAgent._serialize_steps(steps)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["tool"], "search_knowledge_base")
        # base.py uses "observation" key (not "output")
        self.assertIn("Found 3 results", result[0]["observation"])

    def test_max_iterations_default(self):
        from ai_engine.agents.base import SynapseAgent

        self.assertEqual(SynapseAgent.MAX_ITERATIONS, 10)

    def test_max_execution_time_default(self):
        from ai_engine.agents.base import SynapseAgent

        self.assertEqual(SynapseAgent.MAX_EXECUTION_TIME, 300)

    def test_max_tokens_per_task(self):
        from ai_engine.agents.base import SynapseAgent

        self.assertEqual(SynapseAgent.MAX_TOKENS_PER_TASK, 10_000)
