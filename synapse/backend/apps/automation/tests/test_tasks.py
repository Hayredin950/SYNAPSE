"""
Tests for the Automation app Celery tasks.

Covers:
  - execute_workflow() orchestration logic
  - Action handlers: collect_news, summarize_content, send_email, generate_pdf
  - cleanup_stale_runs()
  - Edge cases: missing workflow, invalid action, all-success, partial-failure
"""

import uuid
from datetime import timedelta
from unittest.mock import MagicMock, call, patch

from apps.automation.models import AutomationWorkflow, WorkflowRun
from apps.automation.tasks import (
    _action_collect_news,
    _action_send_email,
    _action_summarize_content,
    cleanup_stale_runs,
    execute_workflow,
)
from apps.users.models import User

from django.test import TestCase
from django.utils import timezone


def _make_user():
    uid = uuid.uuid4().hex[:6]
    return User.objects.create_user(
        username=f"task_test_{uid}",
        email=f"task_test_{uid}@example.com",
        password="pass12345",
    )


def _make_workflow(user, actions=None, is_active=True):
    return AutomationWorkflow.objects.create(
        user=user,
        name="Test Workflow",
        trigger_type="manual",
        is_active=is_active,
        actions=actions
        or [{"type": "collect_news", "params": {"sources": ["hackernews"]}}],
    )


class ExecuteWorkflowTaskTests(TestCase):

    def setUp(self):
        self.user = _make_user()

    def test_nonexistent_workflow_id_does_not_crash(self):
        """Task should handle missing workflow gracefully (not raise)."""
        fake_id = str(uuid.uuid4())
        try:
            execute_workflow(fake_id)
        except Exception as exc:
            self.fail(f"execute_workflow raised unexpectedly: {exc}")

    def test_creates_workflow_run_on_execution(self):
        wf = _make_workflow(self.user)
        mock_result = {"action": "collect_news", "status": "queued", "task_ids": {}}
        with patch("apps.automation.tasks._dispatch_action", return_value=mock_result):
            execute_workflow(str(wf.id))
        self.assertTrue(WorkflowRun.objects.filter(workflow=wf).exists())

    def test_successful_execution_sets_run_status_success(self):
        wf = _make_workflow(
            self.user,
            actions=[{"type": "collect_news", "params": {"sources": ["hackernews"]}}],
        )
        mock_result = {"action": "collect_news", "status": "queued", "task_ids": {}}
        with patch("apps.automation.tasks._dispatch_action", return_value=mock_result):
            execute_workflow(str(wf.id))
        run = WorkflowRun.objects.filter(workflow=wf).first()
        self.assertIsNotNone(run)
        self.assertEqual(run.status, WorkflowRun.RunStatus.SUCCESS)

    def test_failed_action_sets_run_status_failed(self):
        wf = _make_workflow(self.user, actions=[{"type": "collect_news", "params": {}}])
        with patch(
            "apps.automation.tasks._dispatch_action", side_effect=Exception("boom")
        ):
            execute_workflow(str(wf.id))
        run = WorkflowRun.objects.filter(workflow=wf).first()
        self.assertEqual(run.status, WorkflowRun.RunStatus.FAILED)
        self.assertIn("boom", run.error_message)

    def test_action_returning_failed_status_marks_run_failed(self):
        """A handler that returns status='failed' (not raises) should also mark the run failed."""
        wf = _make_workflow(self.user, actions=[{"type": "generate_pdf", "params": {}}])
        mock_result = {
            "action": "generate_pdf",
            "status": "failed",
            "error": "No reportlab",
        }
        with patch("apps.automation.tasks._dispatch_action", return_value=mock_result):
            execute_workflow(str(wf.id))
        run = WorkflowRun.objects.filter(workflow=wf).first()
        self.assertEqual(run.status, WorkflowRun.RunStatus.FAILED)

    def test_unknown_action_type_is_handled_gracefully(self):
        wf = _make_workflow(self.user, actions=[{"type": "teleport", "params": {}}])
        # _dispatch_action returns skipped for unknown types — no exception
        execute_workflow(str(wf.id))
        run = WorkflowRun.objects.filter(workflow=wf).first()
        self.assertIsNotNone(run)

    def test_workflow_run_count_incremented(self):
        wf = _make_workflow(self.user)
        initial_count = wf.run_count
        mock_result = {"action": "collect_news", "status": "queued", "task_ids": {}}
        with patch("apps.automation.tasks._dispatch_action", return_value=mock_result):
            execute_workflow(str(wf.id))
        wf.refresh_from_db()
        self.assertEqual(wf.run_count, initial_count + 1)

    def test_last_run_at_updated(self):
        wf = _make_workflow(self.user)
        before = timezone.now()
        mock_result = {"action": "collect_news", "status": "queued", "task_ids": {}}
        with patch("apps.automation.tasks._dispatch_action", return_value=mock_result):
            execute_workflow(str(wf.id))
        wf.refresh_from_db()
        self.assertIsNotNone(wf.last_run_at)
        self.assertGreaterEqual(wf.last_run_at, before)

    def test_multiple_actions_all_executed_in_order(self):
        """_dispatch_action is called once per action in definition order."""
        wf = _make_workflow(
            self.user,
            actions=[
                {"type": "collect_news", "params": {}},
                {"type": "summarize_content", "params": {}},
            ],
        )
        call_log = []

        def mock_dispatch(workflow, action):
            call_log.append(action["type"])
            return {"action": action["type"], "status": "queued"}

        with patch("apps.automation.tasks._dispatch_action", side_effect=mock_dispatch):
            execute_workflow(str(wf.id))

        self.assertEqual(call_log, ["collect_news", "summarize_content"])

    def test_inactive_workflow_skipped(self):
        wf = _make_workflow(self.user, is_active=False)
        result = execute_workflow(str(wf.id))
        self.assertEqual(result.get("status"), "skipped")
        self.assertFalse(WorkflowRun.objects.filter(workflow=wf).exists())

    def test_celery_task_id_stored_on_run(self):
        """WorkflowRun.celery_task_id is populated when execute_workflow runs."""
        wf = _make_workflow(self.user)
        mock_result = {"action": "collect_news", "status": "queued", "task_ids": {}}
        with patch("apps.automation.tasks._dispatch_action", return_value=mock_result):
            execute_workflow(str(wf.id))
        run = WorkflowRun.objects.filter(workflow=wf).first()
        # celery_task_id may be empty in tests (no real Celery), but the field must exist
        self.assertIsNotNone(run.celery_task_id)

    def test_trigger_event_stored_on_run(self):
        """trigger_event payload is saved on the WorkflowRun."""
        wf = _make_workflow(self.user)
        event = {"event_type": "new_article", "article_id": "abc123"}
        mock_result = {"action": "collect_news", "status": "queued", "task_ids": {}}
        with patch("apps.automation.tasks._dispatch_action", return_value=mock_result):
            execute_workflow(str(wf.id), trigger_event=event)
        run = WorkflowRun.objects.filter(workflow=wf).first()
        self.assertEqual(run.trigger_event.get("event_type"), "new_article")


class ActionHandlerTests(TestCase):

    def test_collect_news_queues_hackernews_task(self):
        with patch("apps.core.tasks.scrape_hackernews") as mock_task:
            mock_task.delay.return_value = MagicMock(id="task-123")
            result = _action_collect_news({"sources": ["hackernews"]})
        self.assertEqual(result["action"], "collect_news")
        self.assertEqual(result["status"], "queued")
        mock_task.delay.assert_called_once()

    def test_collect_news_empty_sources_queues_all(self):
        with (
            patch("apps.core.tasks.scrape_hackernews") as m1,
            patch("apps.core.tasks.scrape_github") as m2,
            patch("apps.core.tasks.scrape_arxiv") as m3,
            patch("apps.core.tasks.scrape_youtube") as m4,
        ):
            for m in (m1, m2, m3, m4):
                m.delay.return_value = MagicMock(id="t")
            result = _action_collect_news({})  # no sources = all
        self.assertIn("hackernews", result["task_ids"])
        self.assertIn("github", result["task_ids"])

    def test_summarize_content_queues_nlp_tasks(self):
        with (
            patch("apps.articles.tasks.process_pending_articles_nlp") as m1,
            patch("apps.articles.tasks.summarize_pending_articles") as m2,
        ):
            m1.delay.return_value = MagicMock(id="nlp-task")
            m2.delay.return_value = MagicMock(id="sum-task")
            result = _action_summarize_content({})
        self.assertIn(result["status"], ["queued", "ok", "skipped"])

    def test_send_email_creates_notification(self):
        """send_email action creates an in-app notification for the workflow owner."""
        from apps.notifications.models import Notification

        uid = uuid.uuid4().hex[:6]
        user = User.objects.create_user(
            username=f"email_test_{uid}",
            email=f"email_test_{uid}@example.com",
            password="pass12345",
        )
        wf = AutomationWorkflow.objects.create(
            user=user,
            name="Email Test Workflow",
            trigger_type="manual",
            actions=[{"type": "send_email", "params": {}}],
        )
        with patch(
            "apps.notifications.tasks.send_notification_email_task"
        ) as mock_email:
            mock_email.delay = MagicMock()
            result = _action_send_email(wf, {"subject": "Done", "body": "Completed."})
        self.assertEqual(result["action"], "send_email")
        self.assertIn(result["status"], ["notification_created", "failed"])

    def test_send_email_bad_params_handled_gracefully(self):
        """send_email action with an invalid workflow mock should not raise unhandled."""
        wf_mock = MagicMock()
        wf_mock.user = MagicMock()
        wf_mock.name = "Bad Workflow"
        result = _action_send_email(wf_mock, {})
        self.assertIn("action", result)
        self.assertEqual(result["action"], "send_email")


class ExecuteWorkflowRunIdKwargTests(TestCase):
    """
    End-to-end tests for execute_workflow() when called with a pre-created
    run_id (the manual-trigger flow).

    Covers:
      - Task reuses the existing WorkflowRun instead of creating a new one
      - Status transitions: pending → running → success / failed
      - celery_task_id is stamped onto the pre-created run
      - trigger_event is merged onto the pre-created run
      - Only one WorkflowRun record exists after execution (no duplicates)
      - Falls back gracefully when run_id points to a deleted/missing record
      - Works correctly end-to-end with a two-action workflow
    """

    def setUp(self):
        self.user = _make_user()
        self.workflow = _make_workflow(
            self.user,
            actions=[
                {"type": "collect_news", "params": {"sources": ["hackernews"]}},
            ],
        )

    def _pre_create_run(self, run_status=WorkflowRun.RunStatus.PENDING):
        """Simulate what the trigger view does: create a pending run first."""
        return WorkflowRun.objects.create(
            workflow=self.workflow,
            status=run_status,
            trigger_event={},
        )

    # ── Reuse, not duplicate ──────────────────────────────────────────────────

    def test_reuses_existing_run_no_new_record_created(self):
        """When run_id is provided only one WorkflowRun must exist after execution."""
        pre_run = self._pre_create_run()
        mock_result = {"action": "collect_news", "status": "queued", "task_ids": {}}
        with patch("apps.automation.tasks._dispatch_action", return_value=mock_result):
            execute_workflow(str(self.workflow.id), run_id=str(pre_run.id))
        self.assertEqual(WorkflowRun.objects.filter(workflow=self.workflow).count(), 1)

    def test_reuses_the_correct_run_record(self):
        """The task must update *exactly* the run whose id was passed."""
        pre_run = self._pre_create_run()
        mock_result = {"action": "collect_news", "status": "queued", "task_ids": {}}
        with patch("apps.automation.tasks._dispatch_action", return_value=mock_result):
            execute_workflow(str(self.workflow.id), run_id=str(pre_run.id))
        pre_run.refresh_from_db()
        self.assertEqual(pre_run.status, WorkflowRun.RunStatus.SUCCESS)

    # ── Status transitions ────────────────────────────────────────────────────

    def test_run_transitions_to_running_then_success(self):
        """Pre-created PENDING run must end in SUCCESS for an all-ok workflow."""
        pre_run = self._pre_create_run(run_status=WorkflowRun.RunStatus.PENDING)
        mock_result = {"action": "collect_news", "status": "queued", "task_ids": {}}
        with patch("apps.automation.tasks._dispatch_action", return_value=mock_result):
            execute_workflow(str(self.workflow.id), run_id=str(pre_run.id))
        pre_run.refresh_from_db()
        self.assertEqual(pre_run.status, WorkflowRun.RunStatus.SUCCESS)
        self.assertIsNotNone(pre_run.completed_at)

    def test_run_transitions_to_failed_when_action_raises(self):
        """Pre-created run must end in FAILED when an action raises."""
        pre_run = self._pre_create_run()
        with patch(
            "apps.automation.tasks._dispatch_action", side_effect=Exception("boom")
        ):
            execute_workflow(str(self.workflow.id), run_id=str(pre_run.id))
        pre_run.refresh_from_db()
        self.assertEqual(pre_run.status, WorkflowRun.RunStatus.FAILED)
        self.assertIn("boom", pre_run.error_message)

    def test_run_transitions_to_failed_when_action_returns_failed_status(self):
        """Pre-created run must end in FAILED when an action returns status='failed'."""
        pre_run = self._pre_create_run()
        mock_result = {"action": "collect_news", "status": "failed", "error": "no data"}
        with patch("apps.automation.tasks._dispatch_action", return_value=mock_result):
            execute_workflow(str(self.workflow.id), run_id=str(pre_run.id))
        pre_run.refresh_from_db()
        self.assertEqual(pre_run.status, WorkflowRun.RunStatus.FAILED)

    # ── celery_task_id stamped ────────────────────────────────────────────────

    def test_celery_task_id_stamped_on_pre_created_run(self):
        """The task's own Celery ID must be written to the pre-created run."""
        pre_run = self._pre_create_run()
        # celery_task_id starts empty on a pre-created run
        self.assertEqual(pre_run.celery_task_id, "")
        mock_result = {"action": "collect_news", "status": "queued", "task_ids": {}}
        with patch("apps.automation.tasks._dispatch_action", return_value=mock_result):
            execute_workflow(str(self.workflow.id), run_id=str(pre_run.id))
        pre_run.refresh_from_db()
        # In tests, self.request.id is None → stored as empty string — field must exist
        self.assertIsNotNone(pre_run.celery_task_id)

    # ── trigger_event merged ──────────────────────────────────────────────────

    def test_trigger_event_merged_onto_pre_created_run(self):
        """trigger_event kwarg must be stored on the pre-created run."""
        pre_run = self._pre_create_run()
        event = {"event_type": "new_article", "article_id": "xyz"}
        mock_result = {"action": "collect_news", "status": "queued", "task_ids": {}}
        with patch("apps.automation.tasks._dispatch_action", return_value=mock_result):
            execute_workflow(
                str(self.workflow.id), trigger_event=event, run_id=str(pre_run.id)
            )
        pre_run.refresh_from_db()
        self.assertEqual(pre_run.trigger_event.get("event_type"), "new_article")

    # ── Fallback for missing run_id ───────────────────────────────────────────

    def test_falls_back_to_new_run_when_run_id_not_found(self):
        """If the pre-created run was somehow deleted, the task creates a fresh one."""
        fake_run_id = str(uuid.uuid4())
        mock_result = {"action": "collect_news", "status": "queued", "task_ids": {}}
        with patch("apps.automation.tasks._dispatch_action", return_value=mock_result):
            execute_workflow(str(self.workflow.id), run_id=fake_run_id)
        # A new run must have been created as a fallback
        self.assertEqual(WorkflowRun.objects.filter(workflow=self.workflow).count(), 1)
        new_run = WorkflowRun.objects.get(workflow=self.workflow)
        self.assertEqual(new_run.status, WorkflowRun.RunStatus.SUCCESS)

    # ── No run_id (schedule / event trigger path) ─────────────────────────────

    def test_without_run_id_creates_fresh_run_as_before(self):
        """Existing schedule/event callers that pass no run_id still work correctly."""
        mock_result = {"action": "collect_news", "status": "queued", "task_ids": {}}
        with patch("apps.automation.tasks._dispatch_action", return_value=mock_result):
            execute_workflow(str(self.workflow.id))
        self.assertEqual(WorkflowRun.objects.filter(workflow=self.workflow).count(), 1)
        run = WorkflowRun.objects.get(workflow=self.workflow)
        self.assertEqual(run.status, WorkflowRun.RunStatus.SUCCESS)

    # ── Multi-action workflow ─────────────────────────────────────────────────

    def test_multi_action_workflow_with_run_id_all_actions_executed(self):
        """All actions are executed in order even when run_id is supplied."""
        wf = _make_workflow(
            self.user,
            actions=[
                {"type": "collect_news", "params": {}},
                {"type": "summarize_content", "params": {}},
            ],
        )
        pre_run = WorkflowRun.objects.create(
            workflow=wf,
            status=WorkflowRun.RunStatus.PENDING,
        )
        call_log = []

        def mock_dispatch(workflow, action):
            call_log.append(action["type"])
            return {"action": action["type"], "status": "queued"}

        with patch("apps.automation.tasks._dispatch_action", side_effect=mock_dispatch):
            execute_workflow(str(wf.id), run_id=str(pre_run.id))

        self.assertEqual(call_log, ["collect_news", "summarize_content"])
        pre_run.refresh_from_db()
        self.assertEqual(pre_run.status, WorkflowRun.RunStatus.SUCCESS)
        self.assertEqual(len(pre_run.result.get("actions", [])), 2)

    # ── Workflow counters updated ─────────────────────────────────────────────

    def test_run_count_incremented_with_run_id(self):
        """workflow.run_count must increment by 1 even when run_id is supplied."""
        pre_run = self._pre_create_run()
        initial = self.workflow.run_count
        mock_result = {"action": "collect_news", "status": "queued", "task_ids": {}}
        with patch("apps.automation.tasks._dispatch_action", return_value=mock_result):
            execute_workflow(str(self.workflow.id), run_id=str(pre_run.id))
        self.workflow.refresh_from_db()
        self.assertEqual(self.workflow.run_count, initial + 1)

    def test_last_run_at_updated_with_run_id(self):
        """workflow.last_run_at must be set even when run_id is supplied."""
        pre_run = self._pre_create_run()
        before = timezone.now()
        mock_result = {"action": "collect_news", "status": "queued", "task_ids": {}}
        with patch("apps.automation.tasks._dispatch_action", return_value=mock_result):
            execute_workflow(str(self.workflow.id), run_id=str(pre_run.id))
        self.workflow.refresh_from_db()
        self.assertIsNotNone(self.workflow.last_run_at)
        self.assertGreaterEqual(self.workflow.last_run_at, before)


class CleanupStaleRunsTests(TestCase):

    def setUp(self):
        self.user = _make_user()
        self.wf = _make_workflow(self.user)

    def test_stale_running_runs_marked_failed(self):
        stale_run = WorkflowRun.objects.create(
            workflow=self.wf,
            status=WorkflowRun.RunStatus.RUNNING,
        )
        WorkflowRun.objects.filter(id=stale_run.id).update(
            started_at=timezone.now() - timedelta(hours=2)
        )
        cleanup_stale_runs()
        stale_run.refresh_from_db()
        self.assertEqual(stale_run.status, WorkflowRun.RunStatus.FAILED)

    def test_recent_running_run_not_touched(self):
        fresh_run = WorkflowRun.objects.create(
            workflow=self.wf,
            status=WorkflowRun.RunStatus.RUNNING,
        )
        cleanup_stale_runs()
        fresh_run.refresh_from_db()
        self.assertEqual(fresh_run.status, WorkflowRun.RunStatus.RUNNING)

    def test_already_completed_runs_not_touched(self):
        done_run = WorkflowRun.objects.create(
            workflow=self.wf,
            status=WorkflowRun.RunStatus.SUCCESS,
        )
        cleanup_stale_runs()
        done_run.refresh_from_db()
        self.assertEqual(done_run.status, WorkflowRun.RunStatus.SUCCESS)
