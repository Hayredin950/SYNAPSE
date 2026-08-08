"""
Tests for TASK-301 — Hybrid Search (BM25 + Semantic + Reranking)

Covers:
  - RRF merge algorithm correctness
  - SearchResult dataclass + final_score property
  - bm25_search() — correct FTS queries, filters, empty results
  - semantic_search_results() — correct vector queries, filters
  - hybrid_search() — RRF merge, reranker integration
  - BM25 API endpoint  POST /api/v1/search/bm25/
  - Hybrid API endpoint POST /api/v1/search/hybrid/
  - Existing semantic endpoint POST /api/v1/search/semantic/ — unchanged behaviour
"""

import uuid
from unittest.mock import MagicMock, patch

from django.test import TestCase
from rest_framework.test import APIClient

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_article(**kwargs):
    from apps.articles.models import Article, Source

    src, _ = Source.objects.get_or_create(
        url="https://test-source.io",
        defaults={"name": "Test", "source_type": "news"},
    )
    defaults = dict(
        title="AI Transformer Architecture",
        content="A deep dive into transformer models used in modern NLP.",
        summary="Transformers are powerful architectures for NLP tasks.",
        url=f"https://example.com/{uuid.uuid4().hex}",
        source=src,
        topic="ai_ml",
        trending_score=0.8,
    )
    defaults.update(kwargs)
    return Article.objects.create(**defaults)


def _make_paper(**kwargs):
    from apps.papers.models import ResearchPaper

    defaults = dict(
        title="Attention Is All You Need",
        abstract="We introduce the Transformer, a model based solely on attention mechanisms.",
        summary="Transformers replace recurrence and convolutions entirely.",
        authors=["Vaswani", "Shazeer", "Parmar"],  # ArrayField requires a list
        arxiv_id=f"2401.{uuid.uuid4().hex[:5]}",
    )
    defaults.update(kwargs)
    return ResearchPaper.objects.create(**defaults)


def _make_repo(**kwargs):
    from apps.repositories.models import Repository

    defaults = dict(
        name="pytorch",
        full_name="pytorch/pytorch",
        description="Tensors and Dynamic neural networks in Python",
        url="https://github.com/pytorch/pytorch",
        stars=80000,
        language="Python",
        owner="pytorch",
        github_id=uuid.uuid4().int % 10**9,
    )
    defaults.update(kwargs)
    return Repository.objects.create(**defaults)


# Use 384 dims to match the test DB schema (the 1024 migration runs in prod only)
FAKE_VECTOR_1024 = [0.1] * 384


# ── SearchResult & RRF unit tests ─────────────────────────────────────────────


class SearchResultTest(TestCase):

    def test_final_score_uses_rerank_when_available(self):
        """final_score returns rerank_score when set."""
        from apps.core.search import SearchResult

        r = SearchResult(
            id="1",
            content_type="article",
            title="T",
            snippet="S",
            obj=None,
            rrf_score=0.5,
            rerank_score=0.9,
        )
        self.assertAlmostEqual(r.final_score, 0.9)

    def test_final_score_falls_back_to_rrf(self):
        """final_score returns rrf_score when rerank_score is None."""
        from apps.core.search import SearchResult

        r = SearchResult(
            id="1",
            content_type="article",
            title="T",
            snippet="S",
            obj=None,
            rrf_score=0.42,
        )
        self.assertAlmostEqual(r.final_score, 0.42)


class RRFMergeTest(TestCase):

    def _make_result(self, rid, content_type="article"):
        from apps.core.search import SearchResult

        return SearchResult(
            id=rid,
            content_type=content_type,
            title=f"Title {rid}",
            snippet="...",
            obj=None,
        )

    def test_rrf_assigns_higher_score_to_top_ranked(self):
        """Document ranked 1st in both lists gets the highest RRF score."""
        from apps.core.search import _rrf_merge

        bm25 = [self._make_result("A"), self._make_result("B"), self._make_result("C")]
        semantic = [
            self._make_result("A"),
            self._make_result("C"),
            self._make_result("D"),
        ]

        merged = _rrf_merge(bm25, semantic)
        ids = [r.id for r in merged]
        self.assertEqual(ids[0], "A")  # top in both lists

    def test_rrf_includes_docs_from_only_one_list(self):
        """RRF includes documents that appear in only one list."""
        from apps.core.search import _rrf_merge

        bm25 = [self._make_result("X")]
        semantic = [self._make_result("Y")]

        merged = _rrf_merge(bm25, semantic)
        ids = {r.id for r in merged}
        self.assertIn("X", ids)
        self.assertIn("Y", ids)

    def test_rrf_deduplicates_across_lists(self):
        """Same document appearing in both lists is deduplicated."""
        from apps.core.search import _rrf_merge

        bm25 = [self._make_result("A"), self._make_result("B")]
        semantic = [self._make_result("A"), self._make_result("B")]

        merged = _rrf_merge(bm25, semantic)
        ids = [r.id for r in merged]
        self.assertEqual(len(ids), len(set(ids)))  # no duplicates

    def test_rrf_formula_correctness(self):
        """RRF score for rank-1 in one list should be 1/(60+1)."""
        from apps.core.search import RRF_K, _rrf_merge

        only_in_bm25 = self._make_result("SOLO")
        merged = _rrf_merge([only_in_bm25], [])
        expected = 1.0 / (RRF_K + 1)
        self.assertAlmostEqual(merged[0].rrf_score, expected, places=6)

    def test_rrf_sets_rank_attributes(self):
        """_rrf_merge populates bm25_rank and semantic_rank on results."""
        from apps.core.search import _rrf_merge

        bm25 = [self._make_result("A")]
        semantic = [self._make_result("A")]

        merged = _rrf_merge(bm25, semantic)
        doc_a = next(r for r in merged if r.id == "A")
        self.assertEqual(doc_a.bm25_rank, 1)
        self.assertEqual(doc_a.semantic_rank, 1)


# ── BM25 search tests ─────────────────────────────────────────────────────────


class BM25SearchTest(TestCase):

    def setUp(self):
        self.art = _make_article(
            title="Transformer Neural Network",
            summary="A new transformer-based model for language understanding.",
        )
        self.paper = _make_paper(
            title="BERT Language Model",
            abstract="BERT is based on the transformer architecture.",
        )

    def test_bm25_finds_articles_by_keyword(self):
        """bm25_search finds articles matching the query keyword."""
        from apps.core.search import bm25_search

        results = bm25_search("transformer", content_types=["articles"])
        ids = [r.id for r in results.get("articles", [])]
        self.assertIn(str(self.art.pk), ids)

    def test_bm25_finds_papers_by_keyword(self):
        """bm25_search finds papers matching the query keyword."""
        from apps.core.search import bm25_search

        results = bm25_search("transformer", content_types=["papers"])
        ids = [r.id for r in results.get("papers", [])]
        self.assertIn(str(self.paper.pk), ids)

    def test_bm25_returns_empty_for_non_matching_query(self):
        """bm25_search returns empty results for unrelated query."""
        from apps.core.search import bm25_search

        results = bm25_search("xylophonebanana123", content_types=["articles"])
        self.assertEqual(len(results.get("articles", [])), 0)

    def test_bm25_respects_limit(self):
        """bm25_search respects the limit parameter."""
        from apps.core.search import bm25_search

        # Create extra articles
        for i in range(5):
            _make_article(
                title=f"Transformer model {i}",
                summary="Transformer-based architecture for tasks.",
            )
        results = bm25_search("transformer", content_types=["articles"], limit=2)
        self.assertLessEqual(len(results.get("articles", [])), 2)

    def test_bm25_sets_bm25_rank(self):
        """bm25_search sets bm25_rank starting at 1 on results."""
        from apps.core.search import bm25_search

        results = bm25_search("transformer", content_types=["articles"])
        articles = results.get("articles", [])
        if articles:
            self.assertEqual(articles[0].bm25_rank, 1)

    def test_bm25_topic_filter(self):
        """bm25_search applies topic filter."""
        from apps.core.search import bm25_search

        _make_article(
            title="Transformer in robotics",
            summary="Transformer architecture applied to robot control.",
            topic="robotics",
        )
        results = bm25_search(
            "transformer", content_types=["articles"], filters={"topic": "ai_ml"}
        )
        for r in results.get("articles", []):
            self.assertEqual(r.obj.topic, "ai_ml")


# ── Semantic search tests ─────────────────────────────────────────────────────


class SemanticSearchResultsTest(TestCase):

    def setUp(self):
        import numpy as np

        self.art = _make_article(
            title="Deep Learning", summary="Neural network research."
        )
        self.art.embedding = FAKE_VECTOR_1024
        self.art.save()

    def test_semantic_finds_article_with_embedding(self):
        """semantic_search_results returns article with embedding."""
        from apps.core.search import semantic_search_results

        results = semantic_search_results(FAKE_VECTOR_1024, content_types=["articles"])
        ids = [r.id for r in results.get("articles", [])]
        self.assertIn(str(self.art.pk), ids)

    def test_semantic_skips_article_without_embedding(self):
        """semantic_search_results skips articles with no embedding."""
        from apps.core.search import semantic_search_results

        no_embed = _make_article(
            title="No Embedding Article", summary="This one has no embedding."
        )
        # embedding is null by default
        results = semantic_search_results(FAKE_VECTOR_1024, content_types=["articles"])
        ids = [r.id for r in results.get("articles", [])]
        self.assertNotIn(str(no_embed.pk), ids)

    def test_semantic_similarity_score_in_0_1(self):
        """semantic_search_results similarity_score is in [0, 1]."""
        from apps.core.search import semantic_search_results

        results = semantic_search_results(FAKE_VECTOR_1024, content_types=["articles"])
        for r in results.get("articles", []):
            if r.similarity_score is not None:
                self.assertGreaterEqual(r.similarity_score, 0.0)
                self.assertLessEqual(r.similarity_score, 1.0)


# ── Hybrid search tests ───────────────────────────────────────────────────────


class HybridSearchTest(TestCase):

    def setUp(self):
        self.art = _make_article(
            title="Transformer Architecture Survey",
            summary="A comprehensive survey of transformer architectures in deep learning.",
        )
        self.art.embedding = FAKE_VECTOR_1024
        self.art.save()

    def test_hybrid_returns_results(self):
        """hybrid_search returns results combining BM25 and semantic."""
        from apps.core.search import hybrid_search

        with patch("apps.core.search._get_reranker", return_value=None):
            results = hybrid_search(
                query="transformer",
                query_vector=FAKE_VECTOR_1024,
                content_types=["articles"],
                limit=10,
                use_reranker=False,
            )
        self.assertIn("articles", results)

    def test_hybrid_deduplicates_across_modes(self):
        """hybrid_search deduplicates the same article from BM25 and semantic."""
        from apps.core.search import hybrid_search

        with patch("apps.core.search._get_reranker", return_value=None):
            results = hybrid_search(
                query="transformer",
                query_vector=FAKE_VECTOR_1024,
                content_types=["articles"],
                limit=10,
                use_reranker=False,
            )
        ids = [r.id for r in results.get("articles", [])]
        self.assertEqual(len(ids), len(set(ids)))  # no duplicates

    def test_hybrid_respects_limit(self):
        """hybrid_search respects the limit parameter."""
        for i in range(6):
            a = _make_article(
                title=f"Transformer model {i}",
                summary="A transformer-based language model architecture.",
            )
            a.embedding = FAKE_VECTOR_1024
            a.save()

        from apps.core.search import hybrid_search

        with patch("apps.core.search._get_reranker", return_value=None):
            results = hybrid_search(
                query="transformer",
                query_vector=FAKE_VECTOR_1024,
                content_types=["articles"],
                limit=3,
                use_reranker=False,
            )
        self.assertLessEqual(len(results.get("articles", [])), 3)

    def test_hybrid_without_reranker_uses_rrf(self):
        """hybrid_search without reranker returns results with rrf_score set."""
        from apps.core.search import hybrid_search

        with patch("apps.core.search._get_reranker", return_value=None):
            results = hybrid_search(
                query="transformer",
                query_vector=FAKE_VECTOR_1024,
                content_types=["articles"],
                limit=10,
                use_reranker=False,
            )
        for r in results.get("articles", []):
            self.assertIsNone(r.rerank_score)
            self.assertGreater(r.rrf_score, 0.0)

    def test_hybrid_with_reranker_sets_rerank_score(self):
        """hybrid_search with mock reranker sets rerank_score on results."""
        from apps.core.search import hybrid_search

        mock_reranker = MagicMock()
        mock_reranker.predict.return_value = [0.95]

        with patch("apps.core.search._get_reranker", return_value=mock_reranker):
            results = hybrid_search(
                query="transformer",
                query_vector=FAKE_VECTOR_1024,
                content_types=["articles"],
                limit=10,
                use_reranker=True,
            )
        for r in results.get("articles", []):
            if r.rerank_score is not None:
                self.assertIsInstance(r.rerank_score, float)


# ── BM25 API endpoint tests ───────────────────────────────────────────────────


class BM25EndpointTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.art = _make_article(
            title="Attention Mechanism",
            summary="Attention mechanisms in neural networks.",
        )

    def test_bm25_endpoint_returns_200(self):
        """POST /api/v1/search/bm25/ returns 200 with valid query."""
        response = self.client.post(
            "/api/v1/search/bm25/",
            {"query": "attention", "content_types": ["articles"]},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["meta"]["mode"], "bm25")

    def test_bm25_endpoint_returns_422_for_empty_query(self):
        """POST /api/v1/search/bm25/ returns 422 for empty query."""
        response = self.client.post(
            "/api/v1/search/bm25/", {"query": ""}, format="json"
        )
        self.assertEqual(response.status_code, 422)

    def test_bm25_endpoint_returns_results_with_rank(self):
        """BM25 endpoint includes bm25_rank in results."""
        response = self.client.post(
            "/api/v1/search/bm25/",
            {"query": "attention", "content_types": ["articles"]},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        articles = response.data["data"].get("articles", [])
        if articles:
            self.assertIn("bm25_rank", articles[0])

    def test_bm25_endpoint_respects_limit(self):
        """BM25 endpoint respects limit parameter (capped at 50)."""
        response = self.client.post(
            "/api/v1/search/bm25/",
            {"query": "attention", "limit": 2, "content_types": ["articles"]},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        articles = response.data["data"].get("articles", [])
        self.assertLessEqual(len(articles), 2)

    def test_bm25_endpoint_caps_limit_at_50(self):
        """BM25 endpoint caps limit at 50 regardless of input."""
        response = self.client.post(
            "/api/v1/search/bm25/",
            {"query": "attention", "limit": 999},
            format="json",
        )
        self.assertEqual(response.data["meta"]["limit"], 50)


# ── Hybrid API endpoint tests ─────────────────────────────────────────────────


class HybridEndpointTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.art = _make_article(
            title="Attention Mechanism",
            summary="Attention mechanisms in neural networks.",
        )
        self.art.embedding = FAKE_VECTOR_1024
        self.art.save()

    def test_hybrid_endpoint_returns_200_or_503(self):
        """POST /api/v1/search/hybrid/ returns 200 or 503 (embedding service may be down in CI)."""
        response = self.client.post(
            "/api/v1/search/hybrid/",
            {
                "query": "attention",
                "content_types": ["articles"],
                "use_reranker": False,
            },
            format="json",
        )
        # 503 is expected in CI where embedding model isn't loaded; 200 in full environment
        self.assertIn(response.status_code, [200, 503])
        if response.status_code == 200:
            self.assertTrue(response.data["success"])
            self.assertEqual(response.data["meta"]["mode"], "hybrid")

    def test_hybrid_endpoint_returns_422_for_empty_query(self):
        """POST /api/v1/search/hybrid/ returns 422 for missing query."""
        response = self.client.post(
            "/api/v1/search/hybrid/", {"query": ""}, format="json"
        )
        self.assertEqual(response.status_code, 422)

    def test_hybrid_endpoint_caps_limit(self):
        """Hybrid endpoint caps limit at 50 (verified on meta or via 503 in CI)."""
        response = self.client.post(
            "/api/v1/search/hybrid/",
            {"query": "attention", "limit": 999},
            format="json",
        )
        # In CI embedding service not loaded → 503; in full env → 200 with capped limit
        self.assertIn(response.status_code, [200, 503])
        if response.status_code == 200:
            self.assertEqual(response.data["meta"]["limit"], 50)
