"""
TASK-305 — Daily AI Briefing tests.

Covers:
  B1 — DailyBriefing model (unique constraint, str repr)
  B2 — generate_daily_briefings Celery task (creates/skips briefings)
  B3 — GET /api/briefing/today/ and GET /api/briefing/history/ endpoints
"""

import uuid
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

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


# ─────────────────────── B3: API endpoint tests ──────────────────────────────


@pytest.mark.django_db
class TestTodayBriefingView:

    def test_unauthenticated_returns_401(self, client):
        url = reverse("briefing-today")
        resp = client.get(url)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_returns_404_when_no_briefing(self, auth_client):
        url = reverse("briefing-today")
        resp = auth_client.get(url)
        assert resp.status_code == status.HTTP_404_NOT_FOUND
        assert "error" in resp.data

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
        """Another authenticated user gets 404 for their own (non-existent) briefing."""
        other = User.objects.create_user(
            username="other_user", email="other@x.com", password="pass"
        )
        from rest_framework_simplejwt.tokens import RefreshToken

        token = RefreshToken.for_user(other)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
        url = reverse("briefing-today")
        resp = client.get(url)
        assert resp.status_code == status.HTTP_404_NOT_FOUND


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
