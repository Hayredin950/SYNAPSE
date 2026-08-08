"""
Tests for TASK-201 — Weekly AI Digest email.

Covers:
  - send_weekly_digest_email() HTML/plain generation
  - send_weekly_digest_task() Celery task logic
  - send_weekly_digest_to_all() fan-out task
  - GET/PATCH /api/v1/auth/me/digest/ endpoint
"""

import uuid
from datetime import timedelta
from unittest.mock import MagicMock, patch

from apps.users.models import User

from django.test import TestCase
from django.utils import timezone

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_user(**kwargs):
    defaults = dict(
        username=f"user_{uuid.uuid4().hex[:8]}",
        email=f"{uuid.uuid4().hex[:8]}@example.com",
        digest_enabled=True,
        digest_day="monday",
        is_active=True,
    )
    defaults.update(kwargs)
    return User.objects.create_user(password="testpass123", **defaults)


def _make_article(title="AI Breakthrough", trending_score=99):
    a = MagicMock()
    a.title = title
    a.summary = "A short summary of the article."
    a.topic = "ai_ml"
    return a


def _make_paper(title="Attention Is All You Need"):
    p = MagicMock()
    p.title = title
    p.authors = ["A. Vaswani", "N. Shazeer"]
    return p


def _make_repo(name="openai/gpt-4", stars=50_000, language="Python"):
    r = MagicMock()
    r.name = name
    r.stars = stars
    r.language = language
    r.description = "The best repo ever."
    return r


# ── email_service tests ───────────────────────────────────────────────────────


class SendWeeklyDigestEmailTest(TestCase):

    def setUp(self):
        self.user = _make_user(first_name="Alice")

    @patch("apps.notifications.email_service.send_mail")
    def test_sends_email_with_content(self, mock_send):
        """send_weekly_digest_email() calls send_mail with subject and recipients."""
        from apps.notifications.email_service import send_weekly_digest_email

        mock_send.return_value = 1
        result = send_weekly_digest_email(
            user=self.user,
            articles=[_make_article()],
            papers=[_make_paper()],
            repos=[_make_repo()],
        )

        self.assertTrue(result)
        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args
        self.assertIn(
            "Weekly SYNAPSE Digest",
            call_kwargs[1]["subject"] if call_kwargs[1] else call_kwargs[0][0],
        )

    @patch("apps.notifications.email_service.send_mail")
    def test_sends_with_empty_sections(self, mock_send):
        """send_weekly_digest_email() handles empty content lists gracefully."""
        from apps.notifications.email_service import send_weekly_digest_email

        mock_send.return_value = 1
        result = send_weekly_digest_email(
            user=self.user,
            articles=[],
            papers=[],
            repos=[],
        )
        self.assertTrue(result)

    @patch(
        "apps.notifications.email_service.send_mail",
        side_effect=Exception("SMTP error"),
    )
    def test_returns_false_on_smtp_error(self, mock_send):
        """send_weekly_digest_email() returns False when send_mail raises."""
        from apps.notifications.email_service import send_weekly_digest_email

        result = send_weekly_digest_email(
            user=self.user,
            articles=[],
            papers=[],
            repos=[],
        )
        self.assertFalse(result)

    @patch("apps.notifications.email_service.send_mail")
    def test_html_contains_article_title(self, mock_send):
        """HTML email body contains article title."""
        from apps.notifications.email_service import _build_digest_html

        article = _make_article(title="Unique Article XYZ")
        html = _build_digest_html(
            user=self.user,
            articles=[article],
            papers=[],
            repos=[],
        )
        self.assertIn("Unique Article XYZ", html)

    @patch("apps.notifications.email_service.send_mail")
    def test_html_contains_repo_stars(self, mock_send):
        """HTML email body contains formatted star count."""
        from apps.notifications.email_service import _build_digest_html

        repo = _make_repo(stars=12345)
        html = _build_digest_html(
            user=self.user,
            articles=[],
            papers=[],
            repos=[repo],
        )
        self.assertIn("12,345", html)

    @patch("apps.notifications.email_service.send_mail")
    def test_html_contains_user_name(self, mock_send):
        """HTML email greets user by first name."""
        from apps.notifications.email_service import _build_digest_html

        html = _build_digest_html(
            user=self.user,
            articles=[],
            papers=[],
            repos=[],
        )
        self.assertIn("Alice", html)

    @patch("apps.notifications.email_service.send_mail")
    def test_html_fallback_to_email_prefix(self, mock_send):
        """HTML email uses email prefix when first_name is empty."""
        from apps.notifications.email_service import _build_digest_html

        user = _make_user(first_name="")
        html = _build_digest_html(user=user, articles=[], papers=[], repos=[])
        prefix = user.email.split("@")[0]
        self.assertIn(prefix, html)


# ── Celery task tests ─────────────────────────────────────────────────────────


class SendWeeklyDigestTaskTest(TestCase):

    def setUp(self):
        self.user = _make_user(digest_enabled=True, digest_day="monday")

    def test_task_sends_on_success(self):
        """send_weekly_digest_task returns sent status on success."""
        from apps.notifications.tasks import send_weekly_digest_task

        # Patch all the local imports inside the task function
        with (
            patch("apps.notifications.email_service.send_mail", return_value=1),
            patch("apps.articles.models.Article.objects") as mock_art,
            patch("apps.papers.models.ResearchPaper.objects") as mock_pap,
            patch("apps.repositories.models.Repository.objects") as mock_repo,
        ):

            mock_art.filter.return_value.order_by.return_value.__getitem__ = MagicMock(
                return_value=[]
            )
            mock_pap.filter.return_value.order_by.return_value.__getitem__ = MagicMock(
                return_value=[]
            )
            mock_repo.filter.return_value.order_by.return_value.__getitem__ = MagicMock(
                return_value=[]
            )

            result = send_weekly_digest_task(str(self.user.id))

        self.assertEqual(result["status"], "sent")

    def test_task_skips_disabled_user(self):
        """send_weekly_digest_task skips users with digest_enabled=False."""
        self.user.digest_enabled = False
        self.user.save()

        from apps.notifications.tasks import send_weekly_digest_task

        result = send_weekly_digest_task(str(self.user.id))
        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["reason"], "digest_disabled")

    def test_task_handles_unknown_user(self):
        """send_weekly_digest_task returns failed for non-existent user."""
        from apps.notifications.tasks import send_weekly_digest_task

        result = send_weekly_digest_task(str(uuid.uuid4()))
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["reason"], "User not found")


class SendWeeklyDigestToAllTest(TestCase):

    def setUp(self):
        # Monday users
        self.monday_user_1 = _make_user(digest_enabled=True, digest_day="monday")
        self.monday_user_2 = _make_user(digest_enabled=True, digest_day="monday")
        # Friday user — should NOT be enqueued on Monday
        self.friday_user = _make_user(digest_enabled=True, digest_day="friday")
        # Disabled user — should NOT be enqueued
        self.disabled_user = _make_user(digest_enabled=False, digest_day="monday")

    def test_fanout_enqueues_correct_users(self):
        """send_weekly_digest_to_all enqueues only enabled users on matching day."""
        from apps.notifications.tasks import send_weekly_digest_to_all

        # Patch delay so no real Celery tasks are dispatched, and
        # patch django.utils.timezone inside the task's local scope
        with (
            patch("apps.notifications.tasks.send_weekly_digest_task") as mock_task,
            patch("django.utils.timezone.now") as mock_now,
        ):
            mock_now.return_value.strftime.return_value = "monday"
            mock_task.delay = MagicMock()
            result = send_weekly_digest_to_all()

        self.assertEqual(result["status"], "enqueued")
        self.assertEqual(result["day"], "monday")
        # 2 monday-enabled users (not friday_user, not disabled_user)
        self.assertEqual(result["count"], 2)

    def test_fanout_enqueues_zero_on_no_match(self):
        """send_weekly_digest_to_all enqueues 0 when no users match today."""
        from apps.notifications.tasks import send_weekly_digest_to_all

        with (
            patch("apps.notifications.tasks.send_weekly_digest_task") as mock_task,
            patch("django.utils.timezone.now") as mock_now,
        ):
            mock_now.return_value.strftime.return_value = "wednesday"
            mock_task.delay = MagicMock()
            result = send_weekly_digest_to_all()

        self.assertEqual(result["count"], 0)


# ── Digest preference API endpoint tests ──────────────────────────────────────


class DigestPreferencesViewTest(TestCase):

    def setUp(self):
        from rest_framework_simplejwt.tokens import RefreshToken

        from rest_framework.test import APIClient

        self.user = _make_user(digest_enabled=True, digest_day="monday")
        self.client = APIClient()
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
        self.url = "/api/v1/auth/me/digest/"

    def test_get_returns_current_preferences(self):
        """GET /api/v1/auth/me/digest/ returns digest_enabled and digest_day."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["digest_enabled"], True)
        self.assertEqual(response.data["digest_day"], "monday")

    def test_patch_updates_digest_day(self):
        """PATCH updates digest_day successfully."""
        response = self.client.patch(self.url, {"digest_day": "friday"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["digest_day"], "friday")
        self.user.refresh_from_db()
        self.assertEqual(self.user.digest_day, "friday")

    def test_patch_disables_digest(self):
        """PATCH sets digest_enabled=False."""
        response = self.client.patch(self.url, {"digest_enabled": False}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["digest_enabled"], False)
        self.user.refresh_from_db()
        self.assertFalse(self.user.digest_enabled)

    def test_patch_invalid_day_returns_400(self):
        """PATCH with invalid digest_day returns HTTP 400."""
        response = self.client.patch(self.url, {"digest_day": "funday"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.data)

    def test_patch_invalid_enabled_type_returns_400(self):
        """PATCH with non-boolean digest_enabled returns HTTP 400."""
        response = self.client.patch(self.url, {"digest_enabled": "yes"}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_patch_empty_body_returns_400(self):
        """PATCH with no recognised fields returns HTTP 400."""
        response = self.client.patch(self.url, {}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_unauthenticated_returns_401(self):
        """Unauthenticated requests are rejected."""
        from rest_framework.test import APIClient

        unauth = APIClient()
        response = unauth.get(self.url)
        self.assertEqual(response.status_code, 401)
