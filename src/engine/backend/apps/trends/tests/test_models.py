"""
Tests for the Trends app models.
"""

import datetime
import uuid

from apps.trends.models import TechnologyTrend

from django.db import IntegrityError
from django.test import TestCase


class TechnologyTrendModelTests(TestCase):

    def _make_trend(self, name="Python", date=None, score=75.0, category="language"):
        return TechnologyTrend.objects.create(
            technology_name=name,
            date=date or datetime.date.today(),
            trend_score=score,
            mention_count=100,
            category=category,
            sources=["hackernews", "github"],
        )

    def test_create_trend(self):
        t = self._make_trend()
        self.assertIsInstance(t.id, uuid.UUID)
        self.assertEqual(t.technology_name, "Python")
        self.assertEqual(t.trend_score, 75.0)

    def test_str_representation(self):
        today = datetime.date.today()
        t = self._make_trend(date=today)
        self.assertIn("Python", str(t))
        self.assertIn(str(today), str(t))

    def test_unique_constraint_per_day(self):
        today = datetime.date.today()
        self._make_trend(name="Rust", date=today)
        with self.assertRaises(IntegrityError):
            self._make_trend(name="Rust", date=today)

    def test_same_name_different_days_allowed(self):
        d1 = datetime.date(2025, 1, 1)
        d2 = datetime.date(2025, 1, 2)
        t1 = self._make_trend(name="Go", date=d1)
        t2 = self._make_trend(name="Go", date=d2)
        self.assertNotEqual(t1.id, t2.id)

    def test_default_ordering_by_trend_score_desc(self):
        today = datetime.date.today()
        self._make_trend(name="Low", date=today, score=10.0)
        yesterday = today - datetime.timedelta(days=1)
        self._make_trend(name="High", date=yesterday, score=99.0)
        trends = list(TechnologyTrend.objects.all())
        self.assertEqual(trends[0].technology_name, "High")

    def test_sources_is_json_field(self):
        t = self._make_trend()
        t.refresh_from_db()
        self.assertIsInstance(t.sources, list)
        self.assertIn("github", t.sources)

    def test_blank_category_allowed(self):
        t = TechnologyTrend.objects.create(
            technology_name="NoCategory",
            date=datetime.date(2025, 6, 1),
            trend_score=50.0,
        )
        self.assertEqual(t.category, "")

    def test_mention_count_defaults_to_zero(self):
        t = TechnologyTrend.objects.create(
            technology_name="DefaultCount",
            date=datetime.date(2025, 7, 1),
        )
        self.assertEqual(t.mention_count, 0)
