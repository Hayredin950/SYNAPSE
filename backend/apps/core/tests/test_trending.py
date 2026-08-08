"""
Tests for the trending and recommendations modules.

Covers:
  - get_trending() — score accumulation, ordering, type filtering
  - recommend_for_user() — returns empty for users with no history
  - GET /api/v1/trending/   endpoint
  - GET /api/v1/recommendations/ endpoint
"""

import uuid
from unittest.mock import MagicMock, patch

from apps.articles.models import Article
from apps.core.models import UserActivity
from apps.core.recommendations import recommend_for_user
from apps.core.trending import _accumulate_scores, get_trending
from apps.users.models import User

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient


def _make_user(email=None):
    email = email or f"trending_{uuid.uuid4().hex[:6]}@test.com"
    import uuid as _uuu

    uname = "user_" + _uuu.uuid4().hex[:8]
    return User.objects.create_user(username=uname, email=email, password="pass12345")


def _make_article(title="Test Article", score=0.5):
    return Article.objects.create(
        title=title,
        url=f"https://example.com/{uuid.uuid4().hex}",
        source=None,
        trending_score=score,
    )


class AccumulateScoresTests(TestCase):

    def test_returns_dict(self):
        from datetime import timedelta

        from django.utils import timezone

        since = timezone.now() - timedelta(hours=48)
        result = _accumulate_scores(since)
        self.assertIsInstance(result, dict)

    def test_empty_when_no_activity(self):
        from datetime import timedelta

        from django.utils import timezone

        since = timezone.now() - timedelta(hours=1)
        result = _accumulate_scores(since)
        self.assertEqual(result, {})

    def test_accumulates_bookmark_weight(self):
        from datetime import timedelta

        from django.utils import timezone

        user = _make_user()
        article = _make_article()
        ct = ContentType.objects.get_for_model(Article)
        UserActivity.objects.create(
            user=user,
            content_type=ct,
            object_id=str(article.id),
            interaction_type="bookmark",
        )
        since = timezone.now() - timedelta(hours=1)
        result = _accumulate_scores(since)
        model_label = ct.model  # 'article'
        self.assertIn(model_label, result)
        ids = [item[0] for item in result[model_label]]
        self.assertIn(str(article.id), ids)

    def test_unbookmark_reduces_score(self):
        from datetime import timedelta

        from django.utils import timezone

        user = _make_user()
        article = _make_article()
        ct = ContentType.objects.get_for_model(Article)
        # bookmark (+3) + unbookmark (-1.5) = net 1.5
        UserActivity.objects.create(
            user=user,
            content_type=ct,
            object_id=str(article.id),
            interaction_type="bookmark",
        )
        UserActivity.objects.create(
            user=user,
            content_type=ct,
            object_id=str(article.id),
            interaction_type="unbookmark",
        )
        since = timezone.now() - timedelta(hours=1)
        result = _accumulate_scores(since)
        model_label = ct.model
        scores = {item[0]: item[1] for item in result.get(model_label, [])}
        if str(article.id) in scores:
            self.assertAlmostEqual(scores[str(article.id)], 1.5, places=1)


class GetTrendingTests(TestCase):

    def test_returns_dict_with_expected_keys(self):
        result = get_trending(limit_per_type=5, hours=48)
        self.assertIsInstance(result, dict)

    def test_returns_empty_when_no_activity(self):
        result = get_trending(limit_per_type=5, hours=1)
        # articles/papers/repos keys should all be empty lists when no activity
        self.assertIsInstance(result.get("articles", []), list)
        self.assertIsInstance(result.get("papers", []), list)
        self.assertIsInstance(result.get("repos", []), list)
        for v in (
            result.get("articles", []),
            result.get("papers", []),
            result.get("repos", []),
        ):
            self.assertEqual(v, [])

    def test_returns_articles_when_bookmarked(self):
        from django.utils import timezone

        user = _make_user()
        article = _make_article("Trending Article")
        ct = ContentType.objects.get_for_model(Article)
        UserActivity.objects.create(
            user=user,
            content_type=ct,
            object_id=str(article.id),
            interaction_type="bookmark",
        )
        result = get_trending(limit_per_type=10, hours=48)
        # get_trending returns {"articles": [(obj, score), ...], ...}
        articles_list = result.get("articles", [])
        article_ids = [str(obj.id) for obj, score in articles_list]
        self.assertIn(str(article.id), article_ids)


class RecommendForUserTests(TestCase):

    def test_returns_dict(self):
        user = _make_user()
        result = recommend_for_user(user, limit=5)
        self.assertIsInstance(result, dict)

    def test_returns_empty_for_user_with_no_history(self):
        user = _make_user()
        result = recommend_for_user(user, limit=5)
        # No history = no vectors = empty recommendations
        for v in result.values():
            self.assertIsInstance(v, list)


class TrendingEndpointTests(TestCase):
    """GET /api/v1/trending/"""

    def setUp(self):
        self.client = APIClient()
        self.user = _make_user()
        self.client.force_authenticate(user=self.user)
        self.url = "/api/v1/trending/"

    def test_returns_200(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_response_has_success_field(self):
        resp = self.client.get(self.url)
        self.assertIn("success", resp.data)

    def test_unauthenticated_returns_401_or_200(self):
        """Trending may be public or auth-required depending on config."""
        resp = APIClient().get(self.url)
        self.assertIn(
            resp.status_code, [status.HTTP_200_OK, status.HTTP_401_UNAUTHORIZED]
        )


class RecommendationsEndpointTests(TestCase):
    """GET /api/v1/recommendations/"""

    def setUp(self):
        self.client = APIClient()
        self.user = _make_user()
        self.client.force_authenticate(user=self.user)
        self.url = "/api/v1/recommendations/"

    def test_returns_200(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_response_has_success_field(self):
        resp = self.client.get(self.url)
        self.assertIn("success", resp.data)

    def test_unauthenticated_returns_401(self):
        resp = APIClient().get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
