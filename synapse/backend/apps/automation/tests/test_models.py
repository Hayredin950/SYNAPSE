"""
Unit tests for Automation models.
"""

from apps.automation.models import AutomationWorkflow, WorkflowRun
from apps.users.models import User

from django.test import TestCase


class AutomationWorkflowModelTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        self.workflow = AutomationWorkflow.objects.create(
            user=self.user,
            name="Daily Digest",
            description="Collect and summarize daily tech news.",
            trigger_type=AutomationWorkflow.TriggerType.SCHEDULE,
            cron_expression="0 8 * * *",
            actions=[{"type": "collect_news"}, {"type": "summarize_content"}],
            is_active=True,
        )

    def test_workflow_str(self):
        self.assertIn("Daily Digest", str(self.workflow))
        self.assertIn(self.user.email, str(self.workflow))

    def test_workflow_defaults(self):
        self.assertEqual(self.workflow.status, AutomationWorkflow.Status.ACTIVE)
        self.assertEqual(self.workflow.run_count, 0)
        self.assertIsNone(self.workflow.last_run_at)

    def test_workflow_trigger_types(self):
        self.assertEqual(AutomationWorkflow.TriggerType.SCHEDULE, "schedule")
        self.assertEqual(AutomationWorkflow.TriggerType.EVENT, "event")
        self.assertEqual(AutomationWorkflow.TriggerType.MANUAL, "manual")

    def test_workflow_status_choices(self):
        self.assertEqual(AutomationWorkflow.Status.ACTIVE, "active")
        self.assertEqual(AutomationWorkflow.Status.PAUSED, "paused")
        self.assertEqual(AutomationWorkflow.Status.FAILED, "failed")

    def test_workflow_actions_are_list(self):
        self.assertIsInstance(self.workflow.actions, list)
        self.assertEqual(len(self.workflow.actions), 2)
        self.assertEqual(self.workflow.actions[0]["type"], "collect_news")

    def test_workflow_uuid_pk(self):
        import uuid

        self.assertIsInstance(self.workflow.id, uuid.UUID)

    def test_workflow_ordering(self):
        w2 = AutomationWorkflow.objects.create(
            user=self.user,
            name="Second Workflow",
            trigger_type=AutomationWorkflow.TriggerType.MANUAL,
            actions=[{"type": "collect_news"}],
        )
        workflows = list(AutomationWorkflow.objects.all())
        self.assertEqual(workflows[0].id, w2.id)  # newest first


class WorkflowRunModelTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser2",
            email="test2@example.com",
            password="testpass123",
        )
        self.workflow = AutomationWorkflow.objects.create(
            user=self.user,
            name="Test Workflow",
            trigger_type=AutomationWorkflow.TriggerType.MANUAL,
            actions=[{"type": "collect_news"}],
        )
        self.run = WorkflowRun.objects.create(
            workflow=self.workflow,
            status=WorkflowRun.RunStatus.SUCCESS,
            result={"actions": [{"action": "collect_news", "status": "queued"}]},
        )

    def test_run_str_via_fields(self):
        self.assertEqual(self.run.workflow, self.workflow)
        self.assertEqual(self.run.status, WorkflowRun.RunStatus.SUCCESS)

    def test_run_status_choices(self):
        self.assertEqual(WorkflowRun.RunStatus.PENDING, "pending")
        self.assertEqual(WorkflowRun.RunStatus.RUNNING, "running")
        self.assertEqual(WorkflowRun.RunStatus.SUCCESS, "success")
        self.assertEqual(WorkflowRun.RunStatus.FAILED, "failed")

    def test_run_result_is_dict(self):
        self.assertIsInstance(self.run.result, dict)

    def test_run_cascade_delete(self):
        workflow_id = self.workflow.id
        self.workflow.delete()
        self.assertEqual(WorkflowRun.objects.filter(workflow_id=workflow_id).count(), 0)
