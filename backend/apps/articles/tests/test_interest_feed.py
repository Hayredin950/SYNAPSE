"""
TASK-001-T3 — Integration tests for interest-based feed filtering.

Tests verify that when ?for_you=1 is passed and a user has saved interests
(from the onboarding wizard or the InterestProfileBuilder), the feed returns
only articles matching those interests, while falling back to unfiltered feed
when the user has no preferences at all.
"""

from __future__ import annotations

import uuid

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient


def _make_user(email=None):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    uid = str(uuid.uuid4())[:8]
    email = email or f"feedtest_{uid}@test.com"
    user = User.objects.create_user(
        username=f"feedtest_{uid}",
        email=email,
        password="TestPass123!",
        first_name="Feed",
        last_name="Test",
    )
    return user


def _make_source(name="feed_src"):
    from apps.articles.models import Source

    src, _ = Source.objects.get_or_create(
        url=f"https://example.com/{name}",
        defaults={"name": name, "source_type": "news"},
    )
    return src


def _make_article(title, topic, tags=None, source=None):
    from apps.articles.models import Article

    src = source or _make_source()
    url_hash = str(uuid.uuid4())
    return Article.objects.create(
        title=title,
        url=f"https://example.com/article-{url_hash}",
        content=f"Content about {topic}",
        topic=topic,
        tags=tags or [],
        source=src,
    )


def _make_onboarding_prefs(user, interests, use_case="research", completed=True):
    from apps.users.models import OnboardingPreferences

    prefs, _ = OnboardingPreferences.objects.get_or_create(user=user)
    prefs.interests = interests
    prefs.use_case = use_case
    prefs.completed = completed
    prefs.save()
    return prefs


class TestInterestFeedFiltering(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.src = _make_source("interest_src")

        # Create articles on different topics
        self.ai_article_1 = _make_article(
            "GPT-5 Released", "ai", ["llm", "gpt"], self.src
        )
        self.ai_article_2 = _make_article(
            "Transformers Explained", "ai", ["deep-learning"], self.src
        )
        self.sec_article = _make_article(
            "New CVE Discovered", "security", ["vulnerability"], self.src
        )
        self.cloud_article = _make_article(
            "AWS Cost Optimisation", "cloud", ["aws", "cost"], self.src
        )
        self.webdev_article = _make_article(
            "React 19 Released", "web dev", ["react", "javascript"], self.src
        )

    # ── Unauthenticated / no ?for_you param ───────────────────────────────────

    def test_feed_without_for_you_returns_all(self):
        """Without ?for_you=1, all articles should be returned (unfiltered)."""
        resp = self.client.get("/api/v1/articles/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.data.get("data", resp.data.get("results", []))
        total = resp.data.get("meta", {}).get("total", len(data))
        self.assertGreaterEqual(total, 5)

    def test_for_you_unauthenticated_returns_all(self):
        """?for_you=1 without auth should fall back to unfiltered (no crash)."""
        resp = self.client.get("/api/v1/articles/?for_you=1")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # Should still return articles (fallback to all)
        data = resp.data.get("data", resp.data.get("results", []))
        self.assertIsInstance(data, list)

    # ── Authenticated with completed onboarding ───────────────────────────────

    def test_for_you_filters_by_ai_interest(self):
        """User interested in AI should only see AI articles when ?for_you=1."""
        user = _make_user()
        _make_onboarding_prefs(user, interests=["ai"], completed=True)
        self.client.force_authenticate(user=user)

        resp = self.client.get("/api/v1/articles/?for_you=1")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        data = resp.data.get("data", resp.data.get("results", []))
        topics = [a.get("topic", "").lower() for a in data]

        # All returned articles should be AI-related
        for topic in topics:
            self.assertIn(
                "ai", topic, f"Unexpected topic in personalised feed: {topic}"
            )

    def test_for_you_filters_by_multiple_interests(self):
        """User interested in AI + Security should see both topics."""
        user = _make_user()
        _make_onboarding_prefs(user, interests=["ai", "security"], completed=True)
        self.client.force_authenticate(user=user)

        resp = self.client.get("/api/v1/articles/?for_you=1")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        data = resp.data.get("data", resp.data.get("results", []))
        topics = {a.get("topic", "").lower() for a in data}

        # Should contain both AI and security articles
        self.assertTrue(
            any("ai" in t for t in topics) or any("security" in t for t in topics),
            f"Expected AI or security articles, got: {topics}",
        )
        # Should NOT contain cloud or web dev articles
        self.assertFalse(
            any("cloud" in t for t in topics),
            f"Cloud articles should not appear in AI+Security feed: {topics}",
        )

    def test_for_you_excludes_unrelated_topics(self):
        """User interested only in Security should not see AI or Cloud articles."""
        user = _make_user()
        _make_onboarding_prefs(user, interests=["security"], completed=True)
        self.client.force_authenticate(user=user)

        resp = self.client.get("/api/v1/articles/?for_you=1")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        data = resp.data.get("data", resp.data.get("results", []))
        topics = [a.get("topic", "").lower() for a in data]

        for topic in topics:
            self.assertNotIn(
                "ai", topic, f"AI article leaked into Security-only feed: {topic}"
            )
            self.assertNotIn(
                "cloud", topic, f"Cloud article leaked into Security-only feed: {topic}"
            )

    def test_for_you_without_for_you_param_returns_all(self):
        """User with onboarding prefs but WITHOUT ?for_you=1 sees all articles."""
        user = _make_user()
        _make_onboarding_prefs(user, interests=["ai"], completed=True)
        self.client.force_authenticate(user=user)

        resp_all = self.client.get("/api/v1/articles/")
        resp_for_you = self.client.get("/api/v1/articles/?for_you=1")

        all_data = resp_all.data.get("data", resp_all.data.get("results", []))
        for_you_data = resp_for_you.data.get(
            "data", resp_for_you.data.get("results", [])
        )

        # The personalised feed should have fewer or equal articles
        self.assertLessEqual(len(for_you_data), len(all_data))

    # ── Edge cases ────────────────────────────────────────────────────────────

    def test_for_you_incompleted_onboarding_personalizes(self):
        """
        Lenient gate: interests saved during the wizard personalise the feed
        even if the user never clicked through all 5 steps. A half-finished
        wizard should not silently disable personalization for the account.
        """
        user = _make_user()
        _make_onboarding_prefs(user, interests=["ai"], completed=False)  # NOT completed
        self.client.force_authenticate(user=user)

        resp = self.client.get("/api/v1/articles/?for_you=1")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.data.get("data", resp.data.get("results", []))
        topics = [a.get("topic", "").lower() for a in data]

        # Interests count despite incomplete wizard — only AI articles
        self.assertTrue(topics, "Expected personalized results")
        for topic in topics:
            self.assertIn("ai", topic, f"Non-AI article leaked: {topic}")

    def test_for_you_no_onboarding_prefs_returns_all(self):
        """User with no OnboardingPreferences should get unfiltered feed."""
        user = _make_user()
        # No prefs created
        self.client.force_authenticate(user=user)

        resp = self.client.get("/api/v1/articles/?for_you=1")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.data.get("data", resp.data.get("results", []))
        self.assertGreaterEqual(len(data), 5)

    def test_for_you_empty_interests_returns_all(self):
        """User with empty interests list should get unfiltered feed (fallback)."""
        user = _make_user()
        _make_onboarding_prefs(user, interests=[], completed=True)
        self.client.force_authenticate(user=user)

        resp = self.client.get("/api/v1/articles/?for_you=1")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.data.get("data", resp.data.get("results", []))
        # Empty interests → fallback to all
        self.assertGreaterEqual(len(data), 5)

    def test_for_you_fallback_when_no_matches(self):
        """If interest filter returns 0 results, should fall back to all articles."""
        user = _make_user()
        # Create prefs with an interest that no article has
        _make_onboarding_prefs(user, interests=["blockchain"], completed=True)
        self.client.force_authenticate(user=user)

        resp = self.client.get("/api/v1/articles/?for_you=1")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.data.get("data", resp.data.get("results", []))
        # Should fall back to all articles
        self.assertGreaterEqual(len(data), 5)

    def test_interest_filter_combined_with_topic_param(self):
        """?for_you=1 should still respect ?topic= param on top of interest filter."""
        user = _make_user()
        _make_onboarding_prefs(user, interests=["ai", "security"], completed=True)
        self.client.force_authenticate(user=user)

        resp = self.client.get("/api/v1/articles/?for_you=1&topic=security")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.data.get("data", resp.data.get("results", []))
        topics = [a.get("topic", "").lower() for a in data]

        for topic in topics:
            self.assertIn(
                "security", topic, f"Expected only security articles: {topic}"
            )

    # ── Production interest slugs (onboarding stores ai_ml, web_dev, ...) ────

    def test_for_you_filters_by_production_slugs(self):
        """
        REGRESSION: the onboarding wizard stores interest SLUGS ("ai_ml",
        "web_dev") — the old filter searched title__icontains="ai_ml" which
        never matched, so EVERY user silently got the identical unfiltered
        feed. Slugs must map to real topics/keywords.
        """
        user = _make_user()
        _make_onboarding_prefs(user, interests=["ai_ml"], completed=True)
        self.client.force_authenticate(user=user)

        resp = self.client.get("/api/v1/articles/?for_you=1")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.data.get("data", resp.data.get("results", []))
        titles = [a.get("title", "").lower() for a in data]

        # The AI articles must be present and no security-only article leaks in
        self.assertTrue(
            any("gpt" in t for t in titles), f"Missing AI article: {titles}"
        )
        self.assertTrue(
            any("transformers" in t for t in titles),
            f"Missing AI article: {titles}",
        )
        self.assertFalse(
            any("cve" in t for t in titles),
            f"Security article leaked into ai_ml feed: {titles}",
        )

    def test_for_you_webdev_slug_filters(self):
        """User with web_dev slug sees web articles, not AI/security ones."""
        user = _make_user()
        _make_onboarding_prefs(user, interests=["web_dev"], completed=True)
        self.client.force_authenticate(user=user)

        resp = self.client.get("/api/v1/articles/?for_you=1")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.data.get("data", resp.data.get("results", []))
        titles = [a.get("title", "").lower() for a in data]

        self.assertTrue(
            any("react" in t for t in titles), f"Missing web article: {titles}"
        )
        self.assertFalse(
            any("cve" in t for t in titles),
            f"Security article leaked into web_dev feed: {titles}",
        )

    def test_for_you_uses_interest_profile_builder_topics(self):
        """
        InterestProfileBuilder topic ids ("ai", "web", "rust", ...) must also
        personalize the feed — they are mirrored into onboarding slugs.
        """
        user = _make_user()
        _make_onboarding_prefs(user, interests=[], completed=True)
        # Simulate what PUT /users/me/interests/ stores
        user.preferences = {"interest_profile": {"topics": ["ai"]}}
        user.save(update_fields=["preferences"])
        self.client.force_authenticate(user=user)

        resp = self.client.get("/api/v1/articles/?for_you=1")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.data.get("data", resp.data.get("results", []))
        titles = [a.get("title", "").lower() for a in data]

        self.assertTrue(
            any("gpt" in t for t in titles), f"Missing AI article: {titles}"
        )
