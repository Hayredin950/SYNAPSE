"""
backend.apps.trends.tests.test_tasks
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Unit and integration tests for the analyze_trends_task Celery task.

Covers:
  - Task creates TechnologyTrend records from article/repo data
  - update_or_create semantics (idempotent re-runs)
  - Zero-mention technologies are skipped
  - Errors per-technology are handled gracefully (don't abort the task)
  - Category inference
  - Summary dict structure and counts
"""

from __future__ import annotations

import datetime
from unittest.mock import MagicMock, patch

from apps.trends.models import TechnologyTrend
from apps.trends.tasks import (
    TRACKED_TECHNOLOGIES,
    _build_source_list,
    _infer_category,
    _score_technology,
    analyze_trends_task,
)

from django.test import TestCase
from django.utils import timezone


class CategoryInferenceTests(TestCase):
    """_infer_category() maps technology names to categories."""

    def test_language_category(self):
        self.assertEqual(_infer_category("Python"), "language")
        self.assertEqual(_infer_category("Rust"), "language")
        self.assertEqual(_infer_category("TypeScript"), "language")

    def test_ai_ml_category(self):
        self.assertEqual(_infer_category("LLM"), "ai_ml")
        self.assertEqual(_infer_category("RAG"), "ai_ml")
        self.assertEqual(_infer_category("LangChain"), "ai_ml")

    def test_devops_category(self):
        self.assertEqual(_infer_category("Docker"), "devops")
        self.assertEqual(_infer_category("Kubernetes"), "devops")

    def test_web_category(self):
        self.assertEqual(_infer_category("React"), "web")
        self.assertEqual(_infer_category("FastAPI"), "web")

    def test_unknown_falls_back_to_general(self):
        self.assertEqual(_infer_category("SomethingObscure"), "general")


class BuildSourceListTests(TestCase):
    """_build_source_list() returns the right source labels."""

    def test_both_sources(self):
        sources = _build_source_list(5, 3)
        self.assertIn("articles", sources)
        self.assertIn("repositories", sources)

    def test_articles_only(self):
        sources = _build_source_list(5, 0)
        self.assertIn("articles", sources)
        self.assertNotIn("repositories", sources)

    def test_repos_only(self):
        sources = _build_source_list(0, 3)
        self.assertNotIn("articles", sources)
        self.assertIn("repositories", sources)

    def test_no_sources(self):
        sources = _build_source_list(0, 0)
        self.assertEqual(sources, [])


class AnalyzeTrendsTaskTests(TestCase):
    """Integration-style tests for analyze_trends_task using mocked DB queries."""

    def _mock_score(self, mention_count=10, trend_score=12.0, sources=None):
        return {
            "mention_count": mention_count,
            "trend_score": trend_score,
            "sources": sources or ["articles", "repositories"],
        }

    @patch("apps.trends.tasks._score_technology")
    def test_creates_trend_records(self, mock_score):
        """Task should create TechnologyTrend entries for technologies with mentions."""
        mock_score.return_value = self._mock_score(mention_count=5, trend_score=7.0)

        result = analyze_trends_task(technologies=["Python", "Rust"])

        self.assertEqual(result["created"], 2)
        self.assertEqual(result["updated"], 0)
        self.assertEqual(result["skipped"], 0)
        self.assertEqual(result["errors"], 0)
        self.assertEqual(TechnologyTrend.objects.count(), 2)

    @patch("apps.trends.tasks._score_technology")
    def test_skips_zero_mention_technologies(self, mock_score):
        """Technologies with zero mentions should not create DB records."""
        mock_score.return_value = self._mock_score(
            mention_count=0, trend_score=0.0, sources=[]
        )

        result = analyze_trends_task(technologies=["COBOL"])

        self.assertEqual(result["skipped"], 1)
        self.assertEqual(result["created"], 0)
        self.assertEqual(TechnologyTrend.objects.count(), 0)

    @patch("apps.trends.tasks._score_technology")
    def test_updates_existing_records_idempotent(self, mock_score):
        """Re-running the task for the same date should update, not duplicate."""
        today = datetime.date.today()
        TechnologyTrend.objects.create(
            technology_name="Python",
            date=today,
            mention_count=3,
            trend_score=5.0,
            category="language",
            sources=["articles"],
        )
        mock_score.return_value = self._mock_score(mention_count=10, trend_score=15.0)

        result = analyze_trends_task(technologies=["Python"])

        self.assertEqual(result["created"], 0)
        self.assertEqual(result["updated"], 1)
        self.assertEqual(TechnologyTrend.objects.count(), 1)

        trend = TechnologyTrend.objects.get(technology_name="Python", date=today)
        self.assertEqual(trend.mention_count, 10)
        self.assertAlmostEqual(trend.trend_score, 15.0)

    @patch("apps.trends.tasks._score_technology")
    def test_handles_per_technology_errors_gracefully(self, mock_score):
        """An error scoring one technology should not abort the rest."""

        def side_effect(tech, since):
            if tech == "Rust":
                raise Exception("DB error")
            return self._mock_score(mention_count=5)

        mock_score.side_effect = side_effect

        result = analyze_trends_task(technologies=["Python", "Rust"])

        self.assertEqual(result["errors"], 1)
        self.assertEqual(result["created"], 1)
        # Python should still be created
        self.assertTrue(
            TechnologyTrend.objects.filter(technology_name="Python").exists()
        )

    @patch("apps.trends.tasks._score_technology")
    def test_returns_correct_summary_structure(self, mock_score):
        """Result dict must contain all expected keys."""
        mock_score.return_value = self._mock_score(mention_count=5)

        result = analyze_trends_task(technologies=["Python"])

        for key in (
            "date",
            "technologies_analyzed",
            "created",
            "updated",
            "skipped",
            "errors",
        ):
            self.assertIn(key, result)

    @patch("apps.trends.tasks._score_technology")
    def test_uses_tracked_technologies_by_default(self, mock_score):
        """When no technologies argument given, uses TRACKED_TECHNOLOGIES list."""
        mock_score.return_value = self._mock_score(mention_count=0)

        result = analyze_trends_task()

        self.assertEqual(result["technologies_analyzed"], len(TRACKED_TECHNOLOGIES))

    @patch("apps.trends.tasks._score_technology")
    def test_target_date_parameter(self, mock_score):
        """Passing a target_date creates records for that specific date."""
        mock_score.return_value = self._mock_score(mention_count=5)

        custom_date = "2025-06-15"
        analyze_trends_task(technologies=["Python"], target_date=custom_date)

        trend = TechnologyTrend.objects.get(technology_name="Python")
        self.assertEqual(str(trend.date), custom_date)

    @patch("apps.trends.tasks._score_technology")
    def test_trend_score_stored_correctly(self, mock_score):
        """Trend score from _score_technology is persisted in the DB record."""
        mock_score.return_value = self._mock_score(mention_count=20, trend_score=42.5)

        analyze_trends_task(technologies=["LLM"])

        trend = TechnologyTrend.objects.get(technology_name="LLM")
        self.assertAlmostEqual(trend.trend_score, 42.5, places=1)

    @patch("apps.trends.tasks._score_technology")
    def test_category_set_correctly(self, mock_score):
        """Category is inferred from technology name and saved."""
        mock_score.return_value = self._mock_score(mention_count=5)

        analyze_trends_task(technologies=["Docker"])

        trend = TechnologyTrend.objects.get(technology_name="Docker")
        self.assertEqual(trend.category, "devops")


class ScoreTechnologyTests(TestCase):
    """Unit tests for _score_technology — uses real DB with test data."""

    def setUp(self):
        from apps.articles.models import Article
        from apps.repositories.models import Repository

        today = datetime.date.today()
        # Create one article mentioning Python (source is nullable FK)
        Article.objects.create(
            title="Python is great for data science",
            url="https://example.com/python-ds",
            source=None,
            topic="Machine Learning",
            keywords=["python", "data science"],
            sentiment_score=0.5,
        )
        # Create one repo mentioning Python
        Repository.objects.create(
            github_id=99999,
            name="python-ml-toolkit",
            description="A Python toolkit for ML",
            stars=1000,
            forks=100,
            language="Python",
            topics=["python", "machine-learning"],
        )

    def test_finds_article_mentions(self):
        since = datetime.date.today() - datetime.timedelta(days=1)
        result = _score_technology("Python", since)
        self.assertGreaterEqual(result["mention_count"], 1)
        self.assertGreater(result["trend_score"], 0)

    def test_no_mentions_for_obscure_tech(self):
        since = datetime.date.today() - datetime.timedelta(days=1)
        result = _score_technology("ENIAC_COBOL_1958", since)
        self.assertEqual(result["mention_count"], 0)
        self.assertEqual(result["trend_score"], 0.0)

    def test_returns_required_keys(self):
        since = datetime.date.today() - datetime.timedelta(days=1)
        result = _score_technology("Python", since)
        for key in ("mention_count", "trend_score", "sources"):
            self.assertIn(key, result)
