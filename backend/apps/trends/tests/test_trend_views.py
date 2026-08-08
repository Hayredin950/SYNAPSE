"""
backend.apps.trends.tests.test_trend_views
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Tests for the TechnologyTrend API views.

Covers:
  - GET /api/v1/trends/ — list endpoint (public, no auth required)
  - GET /api/v1/trends/<pk>/ — detail endpoint
  - Filtering by category
  - Ordering by trend_score
  - Response shape: {success, count, results}
  - Days filter param
  - Limit param
"""

from __future__ import annotations

import datetime
import uuid

from apps.trends.models import TechnologyTrend

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient


def _make_trend(
    name: str, category: str = "ai_ml", score: float = 50.0, mentions: int = 10
) -> TechnologyTrend:
    return TechnologyTrend.objects.create(
        technology_name=name,
        date=datetime.date.today(),
        mention_count=mentions,
        trend_score=score,
        category=category,
        sources=["articles", "repositories"],
    )


class TrendListViewTests(TestCase):
    """GET /api/v1/trends/ — public endpoint"""

    def setUp(self):
        self.client = APIClient()
        self.url = "/api/v1/trends/"
        _make_trend("Python", "language", 98.5, 45)
        _make_trend("LLM", "ai_ml", 95.0, 38)
        _make_trend("Docker", "devops", 75.0, 22)
        _make_trend("React", "web", 79.0, 26)

    def test_returns_200_without_auth(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_response_has_success_field(self):
        resp = self.client.get(self.url)
        self.assertTrue(resp.data.get("success"))

    def test_response_has_results_list(self):
        resp = self.client.get(self.url)
        self.assertIn("results", resp.data)
        self.assertIsInstance(resp.data["results"], list)

    def test_response_has_count(self):
        resp = self.client.get(self.url)
        self.assertIn("count", resp.data)
        self.assertGreater(resp.data["count"], 0)

    def test_ordered_by_trend_score_desc(self):
        resp = self.client.get(self.url)
        scores = [r["trend_score"] for r in resp.data["results"]]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_filter_by_category(self):
        resp = self.client.get(self.url + "?category=ai_ml")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for r in resp.data["results"]:
            self.assertIn("ai_ml", r["category"])

    def test_limit_param(self):
        resp = self.client.get(self.url + "?limit=2")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertLessEqual(len(resp.data["results"]), 2)

    def test_days_param_excludes_old_records(self):
        """Records older than 'days' should be excluded."""
        old_date = datetime.date.today() - datetime.timedelta(days=90)
        TechnologyTrend.objects.create(
            technology_name="COBOL",
            date=old_date,
            mention_count=1,
            trend_score=1.0,
            category="language",
            sources=[],
        )
        resp = self.client.get(self.url + "?days=7")
        names = [r["technology_name"] for r in resp.data["results"]]
        self.assertNotIn("COBOL", names)

    def test_result_fields(self):
        resp = self.client.get(self.url)
        r = resp.data["results"][0]
        for field in (
            "id",
            "technology_name",
            "date",
            "mention_count",
            "trend_score",
            "category",
            "sources",
        ):
            self.assertIn(field, r)

    def test_invalid_limit_defaults_gracefully(self):
        resp = self.client.get(self.url + "?limit=abc")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_invalid_days_defaults_gracefully(self):
        resp = self.client.get(self.url + "?days=xyz")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


class TrendDetailViewTests(TestCase):
    """GET /api/v1/trends/<pk>/"""

    def setUp(self):
        self.client = APIClient()
        self.trend = _make_trend("Rust", "language", 69.5, 18)
        self.url = f"/api/v1/trends/{self.trend.id}/"

    def test_returns_200(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_returns_correct_technology(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.data["technology_name"], "Rust")

    def test_nonexistent_returns_404(self):
        resp = self.client.get(f"/api/v1/trends/{uuid.uuid4()}/")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
