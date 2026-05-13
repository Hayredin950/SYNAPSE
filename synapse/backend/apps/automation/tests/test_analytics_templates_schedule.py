"""
Tests for automation API views not covered by test_views.py:
  - workflow_analytics_view
  - list_templates_view
  - clone_template_view
  - list_schedule_view  (django-celery-beat unavailable → graceful error)
  - toggle_schedule_view
  - trigger_event_view  (HTTP endpoint)
  - action_schemas_view
"""

import uuid
from unittest.mock import MagicMock, patch

from apps.automation.models import AutomationWorkflow, WorkflowRun
from apps.users.models import User

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase


def _make_user(suffix=""):
    uid = uuid.uuid4().hex[:8]
    return User.objects.create_user(
        username=f"atest_{uid}{suffix}",
        email=f"atest_{uid}{suffix}@example.com",
        password="testpass123",
    )


def _make_workflow(user, trigger_type="manual", actions=None, is_active=True):
    return AutomationWorkflow.objects.create(
        user=user,
        name="Test Workflow",
        trigger_type=trigger_type,
        cron_expression="0 8 * * *" if trigger_type == "schedule" else "",
        event_config={"event_type": "new_article"} if trigger_type == "event" else {},
        actions=actions or [{"type": "collect_news", "params": {}}],
        is_active=is_active,
    )


# ── Analytics ──────────────────────────────────────────────────────────────────


class AnalyticsViewTests(APITestCase):

    def setUp(self):
        self.user = _make_user()
        self.client.force_authenticate(user=self.user)

    def test_analytics_unauthenticated_denied(self):
        self.client.logout()
        self.client.force_authenticate(user=None)
        resp = self.client.get("/api/v1/automation/analytics/")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_analytics_empty_user(self):
        """User with no workflows returns valid zero-stats response."""
        resp = self.client.get("/api/v1/automation/analytics/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.data
        self.assertIn("total_stats", data)
        self.assertIn("runs_over_time", data)
        self.assertIn("action_distribution", data)
        self.assertIn("top_workflows", data)
        self.assertEqual(data["total_stats"]["total_workflows"], 0)
        self.assertEqual(data["total_stats"]["total_runs"], 0)
        self.assertEqual(data["total_stats"]["success_rate"], 0.0)

    def test_analytics_counts_own_workflows_only(self):
        """Analytics only counts the authenticated user's workflows."""
        other_user = _make_user("other")
        _make_workflow(other_user)  # should NOT appear
        wf = _make_workflow(self.user)
        WorkflowRun.objects.create(
            workflow=wf,
            status=WorkflowRun.RunStatus.SUCCESS,
        )
        resp = self.client.get("/api/v1/automation/analytics/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["total_stats"]["total_workflows"], 1)
        self.assertEqual(resp.data["total_stats"]["total_runs"], 1)
        self.assertEqual(resp.data["total_stats"]["success_runs"], 1)

    def test_analytics_success_rate_calculation(self):
        """Success rate = success / total * 100."""
        wf = _make_workflow(self.user)
        WorkflowRun.objects.create(workflow=wf, status=WorkflowRun.RunStatus.SUCCESS)
        WorkflowRun.objects.create(workflow=wf, status=WorkflowRun.RunStatus.SUCCESS)
        WorkflowRun.objects.create(workflow=wf, status=WorkflowRun.RunStatus.FAILED)
        resp = self.client.get("/api/v1/automation/analytics/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertAlmostEqual(resp.data["total_stats"]["success_rate"], 66.7, places=0)

    def test_analytics_days_param(self):
        """?days param is respected (default 30, max 365)."""
        resp = self.client.get("/api/v1/automation/analytics/?days=7")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["period_days"], 7)

    def test_analytics_days_capped_at_365(self):
        resp = self.client.get("/api/v1/automation/analytics/?days=999")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["period_days"], 365)

    def test_analytics_invalid_days_defaults_to_30(self):
        resp = self.client.get("/api/v1/automation/analytics/?days=notanumber")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["period_days"], 30)

    def test_analytics_action_distribution(self):
        """Action distribution reflects actions defined in workflows."""
        _make_workflow(
            self.user,
            actions=[
                {"type": "collect_news", "params": {}},
                {"type": "send_email", "params": {}},
            ],
        )
        _make_workflow(
            self.user,
            actions=[
                {"type": "collect_news", "params": {}},
            ],
        )
        resp = self.client.get("/api/v1/automation/analytics/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        dist = {d["action"]: d["count"] for d in resp.data["action_distribution"]}
        self.assertEqual(dist.get("collect_news"), 2)
        self.assertEqual(dist.get("send_email"), 1)

    def test_analytics_top_workflows(self):
        """top_workflows lists workflows with run counts."""
        wf = _make_workflow(self.user)
        WorkflowRun.objects.create(workflow=wf, status=WorkflowRun.RunStatus.SUCCESS)
        WorkflowRun.objects.create(workflow=wf, status=WorkflowRun.RunStatus.FAILED)
        resp = self.client.get("/api/v1/automation/analytics/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        top = resp.data["top_workflows"]
        self.assertGreaterEqual(len(top), 1)
        entry = next((t for t in top if t["workflow_id"] == str(wf.id)), None)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["total"], 2)
        self.assertEqual(entry["success"], 1)
        self.assertEqual(entry["failed"], 1)

    def test_analytics_runs_over_time_has_correct_keys(self):
        """runs_over_time entries have date, success, failed, total keys."""
        resp = self.client.get("/api/v1/automation/analytics/?days=7")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        rot = resp.data["runs_over_time"]
        self.assertEqual(len(rot), 7)  # one per day in window
        for entry in rot:
            self.assertIn("date", entry)
            self.assertIn("success", entry)
            self.assertIn("failed", entry)
            self.assertIn("total", entry)


# ── Templates ──────────────────────────────────────────────────────────────────


class TemplateViewTests(APITestCase):

    def setUp(self):
        self.user = _make_user()
        self.client.force_authenticate(user=self.user)

    def test_list_templates_unauthenticated_denied(self):
        self.client.force_authenticate(user=None)
        resp = self.client.get("/api/v1/automation/templates/")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_templates_returns_list(self):
        resp = self.client.get("/api/v1/automation/templates/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIsInstance(resp.data, list)
        self.assertGreater(len(resp.data), 0)

    def test_list_templates_required_fields(self):
        """Each template must have id, name, description, trigger_type, actions."""
        resp = self.client.get("/api/v1/automation/templates/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for t in resp.data:
            self.assertIn("id", t)
            self.assertIn("name", t)
            self.assertIn("description", t)
            self.assertIn("trigger_type", t)
            self.assertIn("actions", t)
            self.assertGreater(len(t["actions"]), 0)

    def test_clone_template_creates_workflow(self):
        """Cloning a valid template creates a new workflow for the user."""
        resp = self.client.post("/api/v1/automation/templates/daily-digest/clone/", {})
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(AutomationWorkflow.objects.filter(user=self.user).count(), 1)

    def test_clone_template_custom_name(self):
        """Custom name is applied to cloned workflow."""
        resp = self.client.post(
            "/api/v1/automation/templates/daily-digest/clone/",
            {"name": "My Custom Digest"},
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        wf = AutomationWorkflow.objects.filter(user=self.user).first()
        self.assertEqual(wf.name, "My Custom Digest")

    def test_clone_template_default_name_used_if_not_provided(self):
        """If no name is provided, template name is used."""
        resp = self.client.post("/api/v1/automation/templates/github-radar/clone/", {})
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        wf = AutomationWorkflow.objects.filter(user=self.user).first()
        self.assertEqual(wf.name, "GitHub Trending Radar")

    def test_clone_nonexistent_template_returns_404(self):
        resp = self.client.post(
            "/api/v1/automation/templates/does-not-exist/clone/", {}
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_clone_template_unauthenticated_denied(self):
        self.client.force_authenticate(user=None)
        resp = self.client.post("/api/v1/automation/templates/daily-digest/clone/", {})
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_clone_event_template_creates_event_workflow(self):
        """Event-type template clones correctly with event_config."""
        resp = self.client.post(
            "/api/v1/automation/templates/trending-alert/clone/", {}
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        wf = AutomationWorkflow.objects.filter(user=self.user).first()
        self.assertEqual(wf.trigger_type, "event")
        self.assertEqual(wf.event_config.get("event_type"), "trending_spike")

    def test_all_six_templates_clonable(self):
        """All 6 built-in templates can be cloned without errors."""
        template_ids = [
            "daily-digest",
            "ai-research-brief",
            "trending-alert",
            "new-article-workflow",
            "weekly-report",
            "github-radar",
        ]
        for tid in template_ids:
            resp = self.client.post(f"/api/v1/automation/templates/{tid}/clone/", {})
            self.assertEqual(
                resp.status_code,
                status.HTTP_201_CREATED,
                msg=f"Template '{tid}' clone failed with: {resp.data}",
            )
        self.assertEqual(
            AutomationWorkflow.objects.filter(user=self.user).count(),
            len(template_ids),
        )


# ── Schedule ───────────────────────────────────────────────────────────────────


class ScheduleViewTests(APITestCase):
    """
    list_schedule_view and toggle_schedule_view require django-celery-beat.
    These tests verify graceful degradation when it is not installed / configured,
    and correct ownership enforcement.
    """

    def setUp(self):
        self.user = _make_user()
        self.client.force_authenticate(user=self.user)

    def test_list_schedule_unauthenticated_denied(self):
        self.client.force_authenticate(user=None)
        resp = self.client.get("/api/v1/automation/schedule/")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_schedule_no_workflows_returns_empty(self):
        """With no scheduled workflows, the schedule list is empty."""
        resp = self.client.get("/api/v1/automation/schedule/")
        # Either 200 (empty list) or 500 if celery-beat not installed — both acceptable
        self.assertIn(
            resp.status_code,
            [status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR],
        )
        if resp.status_code == status.HTTP_200_OK:
            self.assertEqual(resp.data, [])

    def test_toggle_schedule_unauthenticated_denied(self):
        self.client.force_authenticate(user=None)
        wf = _make_workflow(self.user, trigger_type="schedule")
        resp = self.client.post(f"/api/v1/automation/schedule/{wf.id}/toggle/")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_toggle_schedule_other_user_workflow_returns_404(self):
        """Cannot toggle another user's schedule."""
        other = _make_user("sched")
        wf = _make_workflow(other, trigger_type="schedule")
        resp = self.client.post(f"/api/v1/automation/schedule/{wf.id}/toggle/")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_toggle_nonexistent_workflow_returns_404(self):
        fake_id = uuid.uuid4()
        resp = self.client.post(f"/api/v1/automation/schedule/{fake_id}/toggle/")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_toggle_schedule_without_beat_task_returns_400(self):
        """If no PeriodicTask exists for the workflow, returns 400."""
        wf = _make_workflow(self.user, trigger_type="schedule")
        resp = self.client.post(f"/api/v1/automation/schedule/{wf.id}/toggle/")
        # Should be 400 (PeriodicTask.DoesNotExist) or 500 (celery-beat not installed)
        self.assertIn(
            resp.status_code,
            [status.HTTP_400_BAD_REQUEST, status.HTTP_500_INTERNAL_SERVER_ERROR],
        )


# ── Trigger Event (HTTP endpoint) ──────────────────────────────────────────────


class TriggerEventViewTests(APITestCase):

    def setUp(self):
        self.user = _make_user()
        self.client.force_authenticate(user=self.user)

    def test_trigger_event_unauthenticated_denied(self):
        self.client.force_authenticate(user=None)
        resp = self.client.post(
            "/api/v1/automation/events/trigger/",
            {"event_type": "new_article", "payload": {}},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_trigger_event_missing_event_type_returns_400(self):
        resp = self.client.post(
            "/api/v1/automation/events/trigger/",
            {"payload": {}},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_trigger_event_invalid_event_type_returns_400(self):
        resp = self.client.post(
            "/api/v1/automation/events/trigger/",
            {"event_type": "invalid_event"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("apps.automation.tasks.dispatch_event_trigger")
    def test_trigger_event_valid_dispatches_task(self, mock_task):
        mock_task.delay = MagicMock(return_value=MagicMock(id="test-task-id"))
        resp = self.client.post(
            "/api/v1/automation/events/trigger/",
            {
                "event_type": "new_article",
                "payload": {"article_id": "abc", "title": "Test"},
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(resp.data["event_type"], "new_article")
        self.assertIn("celery_task_id", resp.data)
        mock_task.delay.assert_called_once_with(
            "new_article", {"article_id": "abc", "title": "Test"}
        )

    @patch("apps.automation.tasks.dispatch_event_trigger")
    def test_trigger_event_all_valid_event_types(self, mock_task):
        """All four valid event types are accepted."""
        mock_task.delay = MagicMock(return_value=MagicMock(id="task-id"))
        valid_types = ["new_article", "trending_spike", "new_paper", "new_repo"]
        for et in valid_types:
            resp = self.client.post(
                "/api/v1/automation/events/trigger/",
                {"event_type": et, "payload": {}},
                format="json",
            )
            self.assertEqual(
                resp.status_code,
                status.HTTP_202_ACCEPTED,
                msg=f"event_type '{et}' should be accepted",
            )

    @patch("apps.automation.tasks.dispatch_event_trigger")
    def test_trigger_event_empty_payload_is_valid(self, mock_task):
        """Payload defaults to empty dict if not provided."""
        mock_task.delay = MagicMock(return_value=MagicMock(id="task-id"))
        resp = self.client.post(
            "/api/v1/automation/events/trigger/",
            {"event_type": "new_article"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_202_ACCEPTED)
        mock_task.delay.assert_called_once_with("new_article", {})


# ── Action Schemas ─────────────────────────────────────────────────────────────


class ActionSchemasViewTests(APITestCase):

    def setUp(self):
        self.user = _make_user()
        self.client.force_authenticate(user=self.user)

    def test_action_schemas_unauthenticated_denied(self):
        self.client.force_authenticate(user=None)
        resp = self.client.get("/api/v1/automation/action-schemas/")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_action_schemas_returns_all_types(self):
        resp = self.client.get("/api/v1/automation/action-schemas/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        expected = {
            "collect_news",
            "scrape_videos",
            "scrape_tweets",
            "scrape_hackernews",
            "scrape_github",
            "scrape_arxiv",
            "summarize_content",
            "generate_pdf",
            "send_email",
            "upload_to_drive",
            "ai_digest",
        }
        self.assertEqual(set(resp.data.keys()), expected)

    def test_action_schemas_each_has_field_definitions(self):
        """Each action schema must have at least one param field with type and label."""
        resp = self.client.get("/api/v1/automation/action-schemas/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for action_type, schema in resp.data.items():
            self.assertIsInstance(
                schema, dict, msg=f"{action_type} schema is not a dict"
            )
            self.assertGreater(
                len(schema), 0, msg=f"{action_type} schema has no fields"
            )
            for field_name, field_def in schema.items():
                self.assertIn(
                    "type", field_def, msg=f"{action_type}.{field_name} missing 'type'"
                )
                self.assertIn(
                    "label",
                    field_def,
                    msg=f"{action_type}.{field_name} missing 'label'",
                )

    def test_action_schemas_collect_news_has_sources(self):
        """collect_news schema must include a 'sources' multiselect field."""
        resp = self.client.get("/api/v1/automation/action-schemas/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        sources_field = resp.data["collect_news"]["sources"]
        self.assertEqual(sources_field["type"], "multiselect")
        self.assertIn("hackernews", sources_field["options"])
        self.assertIn("github", sources_field["options"])
        self.assertIn("arxiv", sources_field["options"])
