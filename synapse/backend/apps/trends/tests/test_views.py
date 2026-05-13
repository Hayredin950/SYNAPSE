"""
Tests for the Trends app REST API views.

Covers:
  - GET /api/v1/trends/          (trend_list)
  - GET /api/v1/trends/<pk>/     (trend_detail)
"""

import datetime
import uuid

from apps.trends.models import TechnologyTrend

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient


def _make_trend(name="Python", date=None, score=75.0, category="language"):
    return TechnologyTrend.objects.create(
        technology_name=name,
        date=date or datetime.date.today(),
        trend_score=score,
        mention_count=50,
        category=category,
        sources=["hackernews"],
    )


class TrendListViewTests(TestCase):
    """GET /api/v1/trends/"""

    def setUp(self):
        self.client = APIClient()
        self.url = "/api/v1/trends/"
        today = datetime.date.today()
        _make_trend("Python", today, score=90.0, category="language")
        _make_trend("Rust", today, score=80.0, category="language")
        _make_trend("Docker", today, score=70.0, category="devops")
        # Old trend outside default 30-day window
        old_date = today - datetime.timedelta(days=60)
        _make_trend("COBOL", old_date, score=5.0, category="language")

    def test_returns_200(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_response_structure(self):
        resp = self.client.get(self.url)
        self.assertIn("success", resp.data)
        self.assertIn("count", resp.data)
        self.assertIn("results", resp.data)
        self.assertTrue(resp.data["success"])

    def test_default_excludes_old_trends(self):
        resp = self.client.get(self.url)
        names = [r["technology_name"] for r in resp.data["results"]]
        self.assertNotIn("COBOL", names)
        self.assertIn("Python", names)

    def test_filter_by_category(self):
        resp = self.client.get(self.url + "?category=devops")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for r in resp.data["results"]:
            self.assertIn("devops", r["category"].lower())

    def test_results_ordered_by_trend_score_desc(self):
        resp = self.client.get(self.url)
        scores = [r["trend_score"] for r in resp.data["results"]]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_days_param_expands_window(self):
        resp = self.client.get(self.url + "?days=90")
        names = [r["technology_name"] for r in resp.data["results"]]
        self.assertIn("COBOL", names)

    def test_limit_param_restricts_results(self):
        resp = self.client.get(self.url + "?limit=2")
        self.assertLessEqual(len(resp.data["results"]), 2)

    def test_invalid_days_param_uses_default(self):
        resp = self.client.get(self.url + "?days=notanumber")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_invalid_limit_param_uses_default(self):
        resp = self.client.get(self.url + "?limit=abc")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_days_capped_at_365(self):
        resp = self.client.get(self.url + "?days=99999")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_limit_capped_at_100(self):
        resp = self.client.get(self.url + "?limit=99999")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertLessEqual(len(resp.data["results"]), 100)

    def test_empty_results_returns_200(self):
        TechnologyTrend.objects.all().delete()
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["count"], 0)
        self.assertEqual(resp.data["results"], [])

    def test_result_fields_present(self):
        resp = self.client.get(self.url)
        if resp.data["results"]:
            r = resp.data["results"][0]
            for field in [
                "id",
                "technology_name",
                "trend_score",
                "mention_count",
                "category",
                "date",
                "sources",
            ]:
                self.assertIn(field, r)

    def test_unauthenticated_allowed(self):
        resp = APIClient().get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


class TrendDetailViewTests(TestCase):
    """GET /api/v1/trends/<pk>/"""

    def setUp(self):
        self.client = APIClient()
        self.trend = _make_trend("TypeScript")

    def _url(self, pk):
        return f"/api/v1/trends/{pk}/"

    def test_get_existing_trend_returns_200(self):
        resp = self.client.get(self._url(self.trend.pk))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["technology_name"], "TypeScript")

    def test_get_nonexistent_trend_returns_404(self):
        resp = self.client.get(self._url(uuid.uuid4()))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_detail_fields_present(self):
        resp = self.client.get(self._url(self.trend.pk))
        for field in [
            "id",
            "technology_name",
            "trend_score",
            "mention_count",
            "category",
            "date",
            "sources",
        ]:
            self.assertIn(field, resp.data)

    def test_unauthenticated_allowed(self):
        resp = APIClient().get(self._url(self.trend.pk))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
