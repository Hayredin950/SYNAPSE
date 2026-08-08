"""
Integration tests for Automation API views.
"""

from unittest.mock import patch

from apps.automation.models import AutomationWorkflow, WorkflowRun
from apps.users.models import User

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase


class WorkflowAPITestCase(APITestCase):
    """Base test case with authenticated user and sample workflow."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        self.other_user = User.objects.create_user(
            username="other",
            email="other@example.com",
            password="testpass123",
        )
        self.client.force_authenticate(user=self.user)

        self.workflow = AutomationWorkflow.objects.create(
            user=self.user,
            name="My Workflow",
            description="Test workflow",
            trigger_type=AutomationWorkflow.TriggerType.SCHEDULE,
            cron_expression="0 * * * *",
            actions=[{"type": "collect_news"}],
            is_active=True,
        )

    # ── List & Create ─────────────────────────────────────────────────────────

    def test_list_workflows_authenticated(self):
        url = reverse("workflow-list-create")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_returns_only_own_workflows(self):
        AutomationWorkflow.objects.create(
            user=self.other_user,
            name="Other Workflow",
            trigger_type=AutomationWorkflow.TriggerType.MANUAL,
            actions=[{"type": "collect_news"}],
        )
        url = reverse("workflow-list-create")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        # Handle custom wrapper, paginated, and plain list responses
        if isinstance(data, dict):
            if "data" in data:
                results = list(data["data"])
            elif "results" in data:
                results = list(data["results"])
            else:
                results = list(data.values())
        elif isinstance(data, list):
            results = data
        else:
            results = list(data)
        names = [item["name"] for item in results]
        self.assertIn("My Workflow", names)
        self.assertNotIn("Other Workflow", names)

    def test_create_workflow_valid(self):
        url = reverse("workflow-list-create")
        payload = {
            "name": "New Workflow",
            "description": "A test",
            "trigger_type": "schedule",
            "cron_expression": "0 8 * * *",
            "actions": [{"type": "collect_news"}],
        }
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "New Workflow")

    def test_create_workflow_missing_cron_for_schedule(self):
        url = reverse("workflow-list-create")
        payload = {
            "name": "Bad Workflow",
            "trigger_type": "schedule",
            "cron_expression": "",
            "actions": [{"type": "collect_news"}],
        }
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_workflow_invalid_action_type(self):
        url = reverse("workflow-list-create")
        payload = {
            "name": "Bad Actions",
            "trigger_type": "manual",
            "actions": [{"type": "invalid_action"}],
        }
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_workflow_empty_actions(self):
        url = reverse("workflow-list-create")
        payload = {
            "name": "Empty Actions",
            "trigger_type": "manual",
            "actions": [],
        }
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthenticated_access_denied(self):
        self.client.force_authenticate(user=None)
        url = reverse("workflow-list-create")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # ── Retrieve / Update / Delete ────────────────────────────────────────────

    def test_retrieve_workflow(self):
        url = reverse("workflow-detail", kwargs={"pk": self.workflow.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "My Workflow")

    def test_retrieve_other_user_workflow_404(self):
        other_wf = AutomationWorkflow.objects.create(
            user=self.other_user,
            name="Other",
            trigger_type=AutomationWorkflow.TriggerType.MANUAL,
            actions=[{"type": "collect_news"}],
        )
        url = reverse("workflow-detail", kwargs={"pk": other_wf.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_workflow(self):
        url = reverse("workflow-detail", kwargs={"pk": self.workflow.id})
        # Provide all required fields for a full valid partial update
        response = self.client.patch(
            url,
            {
                "name": "Updated Name",
                "actions": [{"type": "collect_news"}],
                "cron_expression": "0 * * * *",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Updated Name")

    def test_delete_workflow(self):
        url = reverse("workflow-detail", kwargs={"pk": self.workflow.id})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            AutomationWorkflow.objects.filter(id=self.workflow.id).exists()
        )

    # ── Trigger ───────────────────────────────────────────────────────────────

    @patch("apps.automation.tasks.execute_workflow")
    def test_trigger_workflow(self, mock_task):
        mock_task.apply_async.return_value.id = "mock-task-id"
        url = reverse("workflow-trigger", kwargs={"pk": self.workflow.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertIn("celery_task_id", response.data)
        self.assertIn("run_id", response.data)
        # apply_async called with args=[workflow_id] and kwargs={'run_id': ...}
        call_args = mock_task.apply_async.call_args
        self.assertEqual(call_args.kwargs["args"][0], str(self.workflow.id))
        self.assertIn("run_id", call_args.kwargs["kwargs"])

    def test_trigger_inactive_workflow(self):
        self.workflow.is_active = False
        self.workflow.save()
        url = reverse("workflow-trigger", kwargs={"pk": self.workflow.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # ── Toggle ────────────────────────────────────────────────────────────────

    def test_toggle_workflow_pauses(self):
        url = reverse("workflow-toggle", kwargs={"pk": self.workflow.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["is_active"])
        self.assertEqual(response.data["status"], "paused")

    def test_toggle_workflow_resumes(self):
        self.workflow.is_active = False
        self.workflow.status = AutomationWorkflow.Status.PAUSED
        self.workflow.save()
        url = reverse("workflow-toggle", kwargs={"pk": self.workflow.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["is_active"])

    # ── Run History ───────────────────────────────────────────────────────────

    def test_list_workflow_runs(self):
        WorkflowRun.objects.create(
            workflow=self.workflow,
            status=WorkflowRun.RunStatus.SUCCESS,
        )
        url = reverse("workflow-runs", kwargs={"pk": self.workflow.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_retrieve_run_detail(self):
        run = WorkflowRun.objects.create(
            workflow=self.workflow,
            status=WorkflowRun.RunStatus.SUCCESS,
        )
        url = reverse("run-detail", kwargs={"pk": run.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "success")


# ── WorkflowRunStatusView tests ───────────────────────────────────────────────


class RunStatusViewTests(WorkflowAPITestCase):
    """
    Tests for GET /api/v1/automation/runs/<id>/status/

    Covers:
      - JSON polling response (default, no ?stream=1)
      - All required fields are present in the response
      - run_id returned by trigger is immediately pollable (no race condition)
      - 404 for non-existent runs
      - 404 when another user's run is requested
      - duration_seconds computed correctly for completed runs
      - pending / running / success / failed statuses all serialise correctly
    """

    def _create_run(self, run_status=WorkflowRun.RunStatus.RUNNING, **kwargs):
        """Helper: create a WorkflowRun owned by self.user."""
        return WorkflowRun.objects.create(
            workflow=self.workflow,
            status=run_status,
            **kwargs,
        )

    # ── Basic response shape ──────────────────────────────────────────────────

    def test_status_endpoint_returns_200_for_own_run(self):
        run = self._create_run()
        url = reverse("run-status", kwargs={"pk": run.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_status_response_contains_all_required_fields(self):
        run = self._create_run(run_status=WorkflowRun.RunStatus.RUNNING)
        url = reverse("run-status", kwargs={"pk": run.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        expected_fields = {
            "id",
            "workflow",
            "status",
            "celery_task_id",
            "trigger_event",
            "started_at",
            "completed_at",
            "result",
            "error_message",
            "duration_seconds",
        }
        self.assertTrue(
            expected_fields.issubset(set(response.data.keys())),
            msg=f"Missing fields: {expected_fields - set(response.data.keys())}",
        )

    def test_status_id_matches_requested_run(self):
        run = self._create_run()
        url = reverse("run-status", kwargs={"pk": run.id})
        response = self.client.get(url)
        self.assertEqual(str(response.data["id"]), str(run.id))

    # ── Status values ─────────────────────────────────────────────────────────

    def test_pending_run_status_serialised(self):
        run = self._create_run(run_status=WorkflowRun.RunStatus.PENDING)
        url = reverse("run-status", kwargs={"pk": run.id})
        response = self.client.get(url)
        self.assertEqual(response.data["status"], "pending")

    def test_running_run_status_serialised(self):
        run = self._create_run(run_status=WorkflowRun.RunStatus.RUNNING)
        url = reverse("run-status", kwargs={"pk": run.id})
        response = self.client.get(url)
        self.assertEqual(response.data["status"], "running")

    def test_success_run_status_serialised(self):
        run = self._create_run(run_status=WorkflowRun.RunStatus.SUCCESS)
        url = reverse("run-status", kwargs={"pk": run.id})
        response = self.client.get(url)
        self.assertEqual(response.data["status"], "success")

    def test_failed_run_status_serialised(self):
        run = self._create_run(
            run_status=WorkflowRun.RunStatus.FAILED,
            error_message="Something went wrong",
        )
        url = reverse("run-status", kwargs={"pk": run.id})
        response = self.client.get(url)
        self.assertEqual(response.data["status"], "failed")
        self.assertEqual(response.data["error_message"], "Something went wrong")

    # ── duration_seconds ──────────────────────────────────────────────────────

    def test_duration_seconds_is_none_while_running(self):
        run = self._create_run(run_status=WorkflowRun.RunStatus.RUNNING)
        url = reverse("run-status", kwargs={"pk": run.id})
        response = self.client.get(url)
        self.assertIsNone(response.data["duration_seconds"])

    def test_duration_seconds_computed_for_completed_run(self):
        from datetime import timedelta

        from django.utils import timezone as tz

        run = self._create_run(run_status=WorkflowRun.RunStatus.SUCCESS)
        # Manually set completed_at so duration is exactly 10 s
        WorkflowRun.objects.filter(id=run.id).update(
            completed_at=run.started_at + timedelta(seconds=10)
        )
        run.refresh_from_db()
        url = reverse("run-status", kwargs={"pk": run.id})
        response = self.client.get(url)
        self.assertAlmostEqual(response.data["duration_seconds"], 10.0, delta=0.1)

    # ── Access control ────────────────────────────────────────────────────────

    def test_status_returns_404_for_nonexistent_run(self):
        import uuid

        url = reverse("run-status", kwargs={"pk": uuid.uuid4()})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_status_returns_404_for_other_users_run(self):
        other_wf = AutomationWorkflow.objects.create(
            user=self.other_user,
            name="Other WF",
            trigger_type=AutomationWorkflow.TriggerType.MANUAL,
            actions=[{"type": "collect_news"}],
        )
        other_run = WorkflowRun.objects.create(
            workflow=other_wf,
            status=WorkflowRun.RunStatus.RUNNING,
        )
        url = reverse("run-status", kwargs={"pk": other_run.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_status_requires_authentication(self):
        run = self._create_run()
        self.client.force_authenticate(user=None)
        url = reverse("run-status", kwargs={"pk": run.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # ── run_id returned by trigger is immediately pollable ────────────────────

    @patch("apps.automation.tasks.execute_workflow")
    def test_trigger_run_id_is_immediately_pollable(self, mock_task):
        """
        The run_id returned in the trigger 202 response must already exist in
        the DB so the frontend can call /runs/<run_id>/status/ straight away —
        no race condition waiting for Celery to create the record.
        """
        mock_task.apply_async.return_value.id = "celery-abc"
        trigger_url = reverse("workflow-trigger", kwargs={"pk": self.workflow.id})
        trigger_resp = self.client.post(trigger_url)
        self.assertEqual(trigger_resp.status_code, status.HTTP_202_ACCEPTED)

        run_id = trigger_resp.data["run_id"]
        self.assertIsNotNone(run_id)

        # Poll status immediately — must return 200, not 404
        status_url = reverse("run-status", kwargs={"pk": run_id})
        status_resp = self.client.get(status_url)
        self.assertEqual(status_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(str(status_resp.data["id"]), run_id)

    @patch("apps.automation.tasks.execute_workflow")
    def test_trigger_creates_pending_run_before_celery(self, mock_task):
        """
        The pre-created WorkflowRun must start in PENDING status so the frontend
        can distinguish 'not started yet' from 'running' while waiting for the
        worker to pick up the task.
        """
        mock_task.apply_async.return_value.id = "celery-xyz"
        trigger_url = reverse("workflow-trigger", kwargs={"pk": self.workflow.id})
        trigger_resp = self.client.post(trigger_url)
        run_id = trigger_resp.data["run_id"]

        run = WorkflowRun.objects.get(id=run_id)
        self.assertEqual(run.status, WorkflowRun.RunStatus.PENDING)

    @patch("apps.automation.tasks.execute_workflow")
    def test_trigger_stores_celery_task_id_on_run(self, mock_task):
        """celery_task_id must be persisted on the pre-created run."""
        mock_task.apply_async.return_value.id = "celery-task-999"
        trigger_url = reverse("workflow-trigger", kwargs={"pk": self.workflow.id})
        trigger_resp = self.client.post(trigger_url)
        run_id = trigger_resp.data["run_id"]

        run = WorkflowRun.objects.get(id=run_id)
        self.assertEqual(run.celery_task_id, "celery-task-999")
