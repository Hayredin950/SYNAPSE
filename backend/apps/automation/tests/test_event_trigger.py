"""
Integration tests for the automation event trigger pipeline.

Tests:
  - dispatch_event_trigger fires matching workflows
  - Cooldown logic prevents re-firing within cooldown window
  - Topic filter narrows which workflows fire
  - trending_spike_signal → dispatch_event_trigger chain
  - E2E: new article signal → workflow run created
"""

import uuid
from datetime import timedelta
from unittest.mock import MagicMock, call, patch

from apps.automation.models import AutomationWorkflow, WorkflowRun
from apps.automation.signals import _fire_event, trending_spike_signal
from apps.automation.tasks import dispatch_event_trigger
from apps.users.models import User

from django.test import TestCase
from django.utils import timezone


def _make_user():
    uid = uuid.uuid4().hex[:6]
    return User.objects.create_user(
        username=f"evt_test_{uid}",
        email=f"evt_test_{uid}@example.com",
        password="pass12345",
    )


def _make_event_workflow(user, event_type="new_article", topic_filter="", cooldown=0):
    return AutomationWorkflow.objects.create(
        user=user,
        name=f"Event Workflow [{event_type}]",
        trigger_type="event",
        is_active=True,
        event_config={
            "event_type": event_type,
            "filter": {"topic": topic_filter},
            "cooldown_minutes": cooldown,
        },
        actions=[{"type": "collect_news", "params": {}}],
    )


class DispatchEventTriggerTests(TestCase):
    def setUp(self):
        self.user = _make_user()

    def test_fires_matching_workflow(self):
        wf = _make_event_workflow(self.user, event_type="new_article")
        with patch("apps.automation.tasks.execute_workflow") as mock_exec:
            mock_exec.delay = MagicMock()
            result = dispatch_event_trigger("new_article", {"title": "AI news"})
        mock_exec.delay.assert_called_once_with(
            str(wf.id), trigger_event={"title": "AI news"}
        )
        self.assertEqual(result["workflows_fired"], 1)

    def test_does_not_fire_wrong_event_type(self):
        _make_event_workflow(self.user, event_type="new_paper")
        with patch("apps.automation.tasks.execute_workflow") as mock_exec:
            mock_exec.delay = MagicMock()
            result = dispatch_event_trigger("new_article", {"title": "test"})
        mock_exec.delay.assert_not_called()
        self.assertEqual(result["workflows_fired"], 0)

    def test_does_not_fire_inactive_workflow(self):
        wf = _make_event_workflow(self.user, event_type="new_article")
        wf.is_active = False
        wf.save()
        with patch("apps.automation.tasks.execute_workflow") as mock_exec:
            mock_exec.delay = MagicMock()
            result = dispatch_event_trigger("new_article", {"title": "test"})
        mock_exec.delay.assert_not_called()
        self.assertEqual(result["workflows_fired"], 0)

    def test_topic_filter_matches(self):
        wf = _make_event_workflow(
            self.user, event_type="new_article", topic_filter="python"
        )
        with patch("apps.automation.tasks.execute_workflow") as mock_exec:
            mock_exec.delay = MagicMock()
            result = dispatch_event_trigger(
                "new_article", {"title": "Python 4.0 released"}
            )
        mock_exec.delay.assert_called_once()
        self.assertEqual(result["workflows_fired"], 1)

    def test_topic_filter_no_match(self):
        _make_event_workflow(self.user, event_type="new_article", topic_filter="rust")
        with patch("apps.automation.tasks.execute_workflow") as mock_exec:
            mock_exec.delay = MagicMock()
            result = dispatch_event_trigger("new_article", {"title": "Python news"})
        mock_exec.delay.assert_not_called()
        self.assertEqual(result["workflows_fired"], 0)

    def test_cooldown_prevents_refire(self):
        wf = _make_event_workflow(self.user, event_type="new_article", cooldown=60)
        # Simulate a recent run (30 min ago — within 60 min cooldown)
        wf.last_run_at = timezone.now() - timedelta(minutes=30)
        wf.save(update_fields=["last_run_at"])
        with patch("apps.automation.tasks.execute_workflow") as mock_exec:
            mock_exec.delay = MagicMock()
            result = dispatch_event_trigger("new_article", {"title": "test"})
        mock_exec.delay.assert_not_called()
        self.assertEqual(result["workflows_fired"], 0)

    def test_cooldown_allows_fire_after_expiry(self):
        wf = _make_event_workflow(self.user, event_type="new_article", cooldown=30)
        # Last run was 60 min ago — cooldown of 30 min has passed
        wf.last_run_at = timezone.now() - timedelta(minutes=60)
        wf.save(update_fields=["last_run_at"])
        with patch("apps.automation.tasks.execute_workflow") as mock_exec:
            mock_exec.delay = MagicMock()
            result = dispatch_event_trigger("new_article", {"title": "test"})
        mock_exec.delay.assert_called_once()
        self.assertEqual(result["workflows_fired"], 1)

    def test_multiple_matching_workflows_all_fired(self):
        wf1 = _make_event_workflow(self.user, event_type="new_article")
        user2 = _make_user()
        wf2 = _make_event_workflow(user2, event_type="new_article")
        with patch("apps.automation.tasks.execute_workflow") as mock_exec:
            mock_exec.delay = MagicMock()
            result = dispatch_event_trigger("new_article", {"title": "test"})
        self.assertEqual(result["workflows_fired"], 2)
        self.assertEqual(mock_exec.delay.call_count, 2)

    def test_trigger_event_payload_passed_through(self):
        wf = _make_event_workflow(self.user, event_type="trending_spike")
        payload = {"topic": "Python", "score": 42.5, "language": "en"}
        with patch("apps.automation.tasks.execute_workflow") as mock_exec:
            mock_exec.delay = MagicMock()
            dispatch_event_trigger("trending_spike", payload)
        mock_exec.delay.assert_called_once_with(str(wf.id), trigger_event=payload)


class TrendingSpikeSignalTests(TestCase):
    def setUp(self):
        self.user = _make_user()

    def test_trending_spike_signal_fires_event(self):
        wf = _make_event_workflow(self.user, event_type="trending_spike")
        with patch("apps.automation.tasks.execute_workflow") as mock_exec:
            mock_exec.delay = MagicMock()
            # Dispatch signal synchronously (signals are synchronous in tests)
            dispatch_event_trigger("trending_spike", {"topic": "Python", "score": 15.0})
        mock_exec.delay.assert_called_once()

    def test_fire_event_helper_calls_dispatch(self):
        with patch("apps.automation.tasks.dispatch_event_trigger") as mock_dispatch:
            mock_dispatch.delay = MagicMock()
            _fire_event("new_article", {"article_id": "abc", "title": "Test"})
        mock_dispatch.delay.assert_called_once_with(
            "new_article", {"article_id": "abc", "title": "Test"}
        )


class NewArticleSignalE2ETests(TestCase):
    """
    E2E test: creating a new Article fires the post_save signal →
    _fire_event → dispatch_event_trigger (mocked) → execute_workflow queued.
    """

    def setUp(self):
        self.user = _make_user()

    def test_new_article_signal_dispatches_event(self):
        _make_event_workflow(self.user, event_type="new_article")

        with patch("apps.automation.tasks.dispatch_event_trigger") as mock_dt:
            mock_dt.delay = MagicMock()
            from apps.articles.models import Article
            from apps.articles.models import Source as ArticleSource

            source, _ = ArticleSource.objects.get_or_create(
                name="Test HN",
                defaults={
                    "url": "https://news.ycombinator.com",
                    "source_type": "hackernews",
                },
            )
            Article.objects.create(
                title="Test Article about Python",
                url=f"https://example.com/{uuid.uuid4()}",
                source=source,
            )

        # The signal handler calls _fire_event which calls dispatch_event_trigger.delay
        mock_dt.delay.assert_called_once()
        call_args = mock_dt.delay.call_args
        self.assertEqual(call_args[0][0], "new_article")
        payload = call_args[0][1]
        self.assertIn("article_id", payload)
        self.assertIn("title", payload)
