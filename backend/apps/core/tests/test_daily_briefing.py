"""
TASK-305 — Daily AI Briefing tests.

Covers:
  B1 — DailyBriefing model (unique constraint, str repr)
  B2 — generate_daily_briefings Celery task (creates/skips briefings)
  B3 — GET /api/briefing/today/ and GET /api/briefing/history/ endpoints
"""

from datetime import date, timedelta

import pytest
from apps.core.models import DailyBriefing
from apps.users.models import User

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

# ─────────────────────────── fixtures ────────────────────────────────────────


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username="brieftest",
        email="brieftest@example.com",
        password="testpass123",
        first_name="Alice",
    )


@pytest.fixture
def auth_client(client, user):
    from rest_framework_simplejwt.tokens import RefreshToken

    token = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
    return client


@pytest.fixture
def briefing(db, user):
    return DailyBriefing.objects.create(
        user=user,
        date=timezone.localdate(),
        content="Paragraph one.\n\nParagraph two.\n\nParagraph three.",
        sources=[
            {"title": "Article A", "url": "https://example.com/a", "type": "article"},
            {"title": "Paper B", "url": "https://example.com/b", "type": "paper"},
        ],
        topic_summary={"topics": ["ai", "python"], "sentiment": "positive"},
    )


# ─────────────────────── B1: Model tests ─────────────────────────────────────


@pytest.mark.django_db
class TestDailyBriefingModel:
    def test_str_repr(self, user):
        b = DailyBriefing(user=user, date=date(2026, 4, 3), content="x")
        assert "2026-04-03" in str(b)

    def test_unique_per_user_per_day(self, briefing, user):
        from django.db import IntegrityError

        with pytest.raises(IntegrityError):
            DailyBriefing.objects.create(
                user=user,
                date=timezone.localdate(),  # same date → violates unique_together
                content="Duplicate",
            )

    def test_defaults(self, db, user):
        b = DailyBriefing.objects.create(
            user=user,
            date=timezone.localdate() - timedelta(days=1),
            content="Yesterday",
        )
        assert b.sources == []
        assert b.topic_summary == {}
        assert b.id is not None

    def test_ordering_newest_first(self, db, user):
        today = timezone.localdate()
        yesterday = today - timedelta(days=1)
        DailyBriefing.objects.create(user=user, date=yesterday, content="Old")
        DailyBriefing.objects.create(user=user, date=today, content="New")
        qs = DailyBriefing.objects.filter(user=user)
        assert qs[0].date == today
        assert qs[1].date == yesterday


# ─────────────────────── B2: Celery task tests ───────────────────────────────


@pytest.mark.django_db
class TestGenerateDailyBriefingsTask:

    def _run_task(self):
        """Call the task synchronously via Celery's apply() helper.

        apply() runs the task in the current process/thread without a broker.
        The bind=True self-injection is handled by Celery internally.
        """
        from apps.core.tasks import generate_daily_briefings

        result = generate_daily_briefings.apply()
        return result.get()

    def test_creates_briefing_for_active_user(self, user):
        result = self._run_task()
        assert DailyBriefing.objects.filter(user=user).exists()
        assert result["created"] >= 1

    def test_skips_already_generated(self, briefing, user):
        result = self._run_task()
        # briefing already exists for today → should be skipped
        assert result["skipped"] >= 1
        # No duplicate created
        assert (
            DailyBriefing.objects.filter(user=user, date=timezone.localdate()).count()
            == 1
        )

    def test_inactive_user_skipped(self, db):
        inactive = User.objects.create_user(
            username="inactive_user",
            email="inactive@example.com",
            password="x",
            is_active=False,
        )
        self._run_task()
        assert not DailyBriefing.objects.filter(user=inactive).exists()

    def test_returns_dict_with_counts(self, user):
        result = self._run_task()
        assert "created" in result
        assert "skipped" in result
        assert isinstance(result["created"], int)
        assert isinstance(result["skipped"], int)

    def test_idempotent_upsert(self, user):
        """Running twice on same day must not duplicate rows."""
        self._run_task()
        self._run_task()
        assert (
            DailyBriefing.objects.filter(user=user, date=timezone.localdate()).count()
            == 1
        )


# ─────────────────── B2b: generate_user_briefing personalization ─────────────


@pytest.mark.django_db
class TestGenerateUserBriefingPersonalization:
    """
    Two users with different interests must get different briefings even when
    neither has run scrapers yet (no linked items) — the content-based
    interest filter must kick in before the global fallback.
    """

    def _make_user(self, username, email, first_name="Tester"):
        return User.objects.create_user(
            username=username,
            email=email,
            password="testpass123",
            first_name=first_name,
        )

    def _set_interests(self, user, interests):
        from apps.users.models import OnboardingPreferences

        prefs, _ = OnboardingPreferences.objects.get_or_create(user=user)
        prefs.interests = interests
        prefs.completed = True
        prefs.save()
        return prefs

    def _seed_articles(self):
        from apps.articles.models import Article, Source

        src, _ = Source.objects.get_or_create(
            url="https://example.com/briefing-src",
            defaults={"name": "BriefingSrc", "source_type": "news"},
        )
        ai = Article.objects.create(
            title="GPT-6 Reasoning Breakthrough",
            url="https://example.com/brief-ai",
            content="Deep learning and transformer advances.",
            topic="AI",
            source=src,
        )
        sec = Article.objects.create(
            title="New Zero-Day Exploit in Wild",
            url="https://example.com/brief-sec",
            content="Security researchers found a vulnerability.",
            topic="Security",
            source=src,
        )
        return ai, sec

    def test_different_interests_get_different_briefings(self):
        from apps.core.tasks import generate_user_briefing

        ai_user = self._make_user("brief_ai", "brief-ai@example.com")
        self._set_interests(ai_user, ["ai_ml"])
        sec_user = self._make_user("brief_sec", "brief-sec@example.com")
        self._set_interests(sec_user, ["security"])
        self._seed_articles()

        res_ai = generate_user_briefing.apply(kwargs={"user_id": str(ai_user.id)}).get()
        res_sec = generate_user_briefing.apply(
            kwargs={"user_id": str(sec_user.id)}
        ).get()

        b_ai = DailyBriefing.objects.get(user=ai_user)
        b_sec = DailyBriefing.objects.get(user=sec_user)

        assert res_ai["status"] == "success"
        assert res_sec["status"] == "success"
        # Different interests → different briefings
        assert b_ai.content != b_sec.content
        # AI user's briefing mentions the AI article, not the security one
        assert "GPT-6" in b_ai.content
        assert "Zero-Day" not in b_ai.content
        assert "Zero-Day" in b_sec.content
        assert "GPT-6" not in b_sec.content

    def test_linked_items_take_precedence_over_interests(self):
        from apps.articles.models import UserArticle
        from apps.core.tasks import generate_user_briefing

        user = self._make_user("brief_link", "brief-link@example.com")
        self._set_interests(user, ["ai_ml"])
        ai, sec = self._seed_articles()
        # Link the SECURITY article to this AI-interested user — linked items
        # are the strongest personalization signal.
        UserArticle.objects.create(user=user, article=sec)

        generate_user_briefing.apply(kwargs={"user_id": str(user.id)}).get()

        b = DailyBriefing.objects.get(user=user)
        assert "Zero-Day" in b.content

    def test_no_prefs_falls_back_to_global(self):
        from apps.core.tasks import generate_user_briefing

        user = self._make_user("brief_none", "brief-none@example.com")
        self._seed_articles()

        generate_user_briefing.apply(kwargs={"user_id": str(user.id)}).get()

        b = DailyBriefing.objects.get(user=user)
        assert b.content  # not empty — global fallback

    def test_global_fallback_is_surfaced_in_content(self):
        """When nothing matches the user's interests, the briefing says so
        instead of silently showing the same global feed as everyone else."""
        from apps.core.tasks import generate_user_briefing

        user = self._make_user("brief_global_note", "brief-global-note@example.com")
        self._seed_articles()
        # No onboarding prefs at all → global tier

        generate_user_briefing.apply(kwargs={"user_id": str(user.id)}).get()

        b = DailyBriefing.objects.get(user=user)
        assert "latest global content" in b.content


# ─────────────────────── B3: API endpoint tests ──────────────────────────────


@pytest.mark.django_db
class TestTodayBriefingView:

    def test_unauthenticated_returns_401(self, client):
        url = reverse("briefing-today")
        resp = client.get(url)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_returns_202_when_no_briefing(self, auth_client):
        """Missing briefing → 202 Accepted; the view auto-queues generation."""
        url = reverse("briefing-today")
        resp = auth_client.get(url)
        assert resp.status_code == status.HTTP_202_ACCEPTED
        assert "error" in resp.data
        assert "generat" in resp.data["error"]["message"].lower()

    def test_returns_today_briefing(self, auth_client, briefing):
        url = reverse("briefing-today")
        resp = auth_client.get(url)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.data["data"]
        assert data["content"] == briefing.content
        assert data["date"] == briefing.date.isoformat()
        assert len(data["sources"]) == 2

    def test_response_includes_all_fields(self, auth_client, briefing):
        url = reverse("briefing-today")
        resp = auth_client.get(url)
        data = resp.data["data"]
        for field in (
            "id",
            "date",
            "content",
            "sources",
            "topic_summary",
            "generated_at",
        ):
            assert field in data, f"Missing field: {field}"

    def test_other_user_cannot_see_briefing(self, client, briefing):
        """Another authenticated user gets 202 (own briefing auto-queued), never the owner's."""
        other = User.objects.create_user(
            username="other_user", email="other@x.com", password="pass"
        )
        from rest_framework_simplejwt.tokens import RefreshToken

        token = RefreshToken.for_user(other)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
        url = reverse("briefing-today")
        resp = client.get(url)
        assert resp.status_code == status.HTTP_202_ACCEPTED
        assert "briefing" not in resp.data.get("data", {})


@pytest.mark.django_db
class TestBriefingHistoryView:

    def test_unauthenticated_returns_401(self, client):
        url = reverse("briefing-history")
        resp = client.get(url)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_empty_history(self, auth_client):
        url = reverse("briefing-history")
        resp = auth_client.get(url)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["data"] == []

    def test_returns_up_to_7_briefings(self, db, auth_client, user):
        today = timezone.localdate()
        for i in range(10):
            d = today - timedelta(days=i)
            DailyBriefing.objects.get_or_create(
                user=user, date=d, defaults={"content": f"Day -{i}"}
            )
        url = reverse("briefing-history")
        resp = auth_client.get(url)
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data["data"]) == 7

    def test_history_ordered_newest_first(self, db, auth_client, user):
        today = timezone.localdate()
        for i in range(3):
            DailyBriefing.objects.get_or_create(
                user=user,
                date=today - timedelta(days=i),
                defaults={"content": f"Brief {i}"},
            )
        url = reverse("briefing-history")
        resp = auth_client.get(url)
        dates = [item["date"] for item in resp.data["data"]]
        assert dates == sorted(dates, reverse=True)

    def test_history_only_own_briefings(self, db, client, user):
        today = timezone.localdate()
        other = User.objects.create_user(
            username="spy_user", email="spy@x.com", password="pass"
        )
        DailyBriefing.objects.create(user=other, date=today, content="spy")

        from rest_framework_simplejwt.tokens import RefreshToken

        token = RefreshToken.for_user(user)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
        url = reverse("briefing-history")
        resp = client.get(url)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["data"] == []  # own user has no briefings
