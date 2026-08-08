"""
backend.apps.agents.tests.test_agent_tasks
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Unit tests for the Celery agent task execution logic.

Covers:
  - execute_agent_task happy path (all task_types including document + project)
  - execute_agent_task sets PROCESSING then COMPLETED/FAILED status
  - Notification created on completion
  - cancel_agent_task revokes running task
  - Unknown agent_task_id handled gracefully
  - tool_map includes 'document' and 'project' task types
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from apps.agents.models import AgentTask
from apps.agents.tasks import _notify_user, cancel_agent_task, execute_agent_task
from apps.users.models import User

from django.test import TestCase
from django.utils import timezone as dj_tz


def _make_user(suffix=""):
    uid = suffix or uuid.uuid4().hex[:6]
    return User.objects.create_user(
        username=f"agent_task_{uid}",
        email=f"agent_task_{uid}@example.com",
        password="pass12345",
    )


def _make_task(
    user, task_type="general", prompt="This is a long enough prompt for the agent."
):
    return AgentTask.objects.create(
        user=user,
        task_type=task_type,
        prompt=prompt,
        status=AgentTask.TaskStatus.PENDING,
    )


# ---------------------------------------------------------------------------
# execute_agent_task
# ---------------------------------------------------------------------------


class ExecuteAgentTaskTests(TestCase):

    def setUp(self):
        self.user = _make_user("exec")

    def test_nonexistent_task_id_returns_gracefully(self):
        """Missing AgentTask should return error dict, not raise."""
        fake_id = str(uuid.uuid4())
        result = execute_agent_task(fake_id)
        self.assertFalse(result["success"])
        self.assertIn("not found", result["error"].lower())

    @patch("apps.agents.tasks._notify_user")
    @patch("ai_engine.agents.get_executor")
    def test_successful_execution_sets_completed(self, mock_get_executor, mock_notify):
        """Happy path: task completes → status=completed, result stored."""
        mock_executor = MagicMock()
        mock_executor.run.return_value = {
            "answer": "Here are the latest AI trends.",
            "intermediate_steps": [],
            "tokens_used": 200,
            "cost_usd": 0.000015,
            "execution_time_s": 1.5,
            "success": True,
            "error": None,
        }
        mock_get_executor.return_value = mock_executor

        task = _make_task(self.user)
        execute_agent_task(str(task.id))

        task.refresh_from_db()
        self.assertEqual(task.status, AgentTask.TaskStatus.COMPLETED)
        self.assertEqual(task.result["answer"], "Here are the latest AI trends.")
        self.assertEqual(task.tokens_used, 200)
        self.assertIsNotNone(task.completed_at)

    @patch("apps.agents.tasks._notify_user")
    @patch("ai_engine.agents.get_executor")
    def test_failed_execution_sets_failed_status(self, mock_get_executor, mock_notify):
        """When executor returns success=False, task status → failed."""
        mock_executor = MagicMock()
        mock_executor.run.return_value = {
            "answer": "",
            "intermediate_steps": [],
            "tokens_used": 0,
            "cost_usd": 0.0,
            "execution_time_s": 0.1,
            "success": False,
            "error": "LLM timeout",
        }
        mock_get_executor.return_value = mock_executor

        task = _make_task(self.user)
        execute_agent_task(str(task.id))

        task.refresh_from_db()
        self.assertEqual(task.status, AgentTask.TaskStatus.FAILED)
        self.assertEqual(task.error_message, "LLM timeout")

    @patch("apps.agents.tasks._notify_user")
    @patch("ai_engine.agents.get_executor")
    def test_notification_created_on_success(self, mock_get_executor, mock_notify):
        """_notify_user is called after successful execution."""
        mock_executor = MagicMock()
        mock_executor.run.return_value = {
            "answer": "Done",
            "intermediate_steps": [],
            "tokens_used": 50,
            "cost_usd": 0.0,
            "execution_time_s": 0.5,
            "success": True,
            "error": None,
        }
        mock_get_executor.return_value = mock_executor

        task = _make_task(self.user)
        execute_agent_task(str(task.id))
        mock_notify.assert_called_once()

    # ── tool_map coverage for new task_types ──────────────────────────────

    @patch("apps.agents.tasks._notify_user")
    @patch("ai_engine.agents.get_executor")
    def test_document_task_type_uses_doc_tools(self, mock_get_executor, mock_notify):
        """'document' task_type restricts agent to doc generation tools."""
        mock_executor = MagicMock()
        mock_executor.run.return_value = {
            "answer": "PDF generated.",
            "intermediate_steps": [],
            "tokens_used": 100,
            "cost_usd": 0.0,
            "execution_time_s": 1.0,
            "success": True,
            "error": None,
        }
        mock_get_executor.return_value = mock_executor

        task = _make_task(
            self.user,
            task_type="document",
            prompt="Generate a PDF report on LLMs in 2025.",
        )
        execute_agent_task(str(task.id))

        call_kwargs = mock_executor.run.call_args
        tool_names = call_kwargs[1].get("tool_names") or call_kwargs[0][1]
        self.assertIn("generate_pdf", tool_names)
        self.assertIn("generate_ppt", tool_names)

    @patch("apps.agents.tasks._notify_user")
    @patch("ai_engine.agents.get_executor")
    def test_project_task_type_uses_project_tool(self, mock_get_executor, mock_notify):
        """'project' task_type restricts agent to create_project tool."""
        mock_executor = MagicMock()
        mock_executor.run.return_value = {
            "answer": "Project created.",
            "intermediate_steps": [],
            "tokens_used": 100,
            "cost_usd": 0.0,
            "execution_time_s": 1.0,
            "success": True,
            "error": None,
        }
        mock_get_executor.return_value = mock_executor

        task = _make_task(
            self.user,
            task_type="project",
            prompt="Create a FastAPI microservice project called my-api.",
        )
        execute_agent_task(str(task.id))

        call_kwargs = mock_executor.run.call_args
        tool_names = call_kwargs[1].get("tool_names") or call_kwargs[0][1]
        self.assertIn("create_project", tool_names)

    @patch("apps.agents.tasks._notify_user")
    @patch("ai_engine.agents.get_executor")
    def test_general_task_type_uses_all_tools(self, mock_get_executor, mock_notify):
        """'general' task_type passes tool_names=None (all tools)."""
        mock_executor = MagicMock()
        mock_executor.run.return_value = {
            "answer": "All tools used.",
            "intermediate_steps": [],
            "tokens_used": 100,
            "cost_usd": 0.0,
            "execution_time_s": 1.0,
            "success": True,
            "error": None,
        }
        mock_get_executor.return_value = mock_executor

        task = _make_task(
            self.user,
            task_type="general",
            prompt="Help me find the best Python web framework for 2025.",
        )
        execute_agent_task(str(task.id))

        call_kwargs = mock_executor.run.call_args
        tool_names = call_kwargs[1].get("tool_names")
        self.assertIsNone(tool_names)


# ---------------------------------------------------------------------------
# _notify_user
# ---------------------------------------------------------------------------


class NotifyUserTests(TestCase):

    def setUp(self):
        self.user = _make_user("notify")

    def test_creates_notification_on_success(self):
        from apps.notifications.models import Notification

        task = _make_task(self.user)
        task.tokens_used = 100
        task.cost_usd = 0.0000075

        _notify_user(task, success=True)

        notif = Notification.objects.filter(user=self.user).first()
        self.assertIsNotNone(notif)
        self.assertIn("completed", notif.title)
        self.assertEqual(notif.notif_type, "info")

    def test_creates_notification_on_failure(self):
        from apps.notifications.models import Notification

        task = _make_task(self.user)
        task.tokens_used = 0
        task.cost_usd = 0

        _notify_user(task, success=False)

        notif = Notification.objects.filter(user=self.user).first()
        self.assertIsNotNone(notif)
        self.assertIn("failed", notif.title)


# ---------------------------------------------------------------------------
# cancel_agent_task
# ---------------------------------------------------------------------------


class CancelAgentTaskTests(TestCase):

    def setUp(self):
        self.user = _make_user("cancel")

    def test_cancel_nonexistent_task(self):
        result = cancel_agent_task(str(uuid.uuid4()), "celery-id-xyz")
        self.assertFalse(result["success"])

    def test_cancel_already_completed_task(self):
        task = _make_task(self.user)
        task.status = AgentTask.TaskStatus.COMPLETED
        task.save()

        result = cancel_agent_task(str(task.id), "celery-id")
        self.assertFalse(result["success"])
        self.assertIn("already", result["error"].lower())

    @patch("celery.app.control.Control.revoke")
    def test_cancel_pending_task_marks_failed(self, mock_revoke):
        task = _make_task(self.user)
        task.celery_task_id = str(uuid.uuid4())
        task.save()

        result = cancel_agent_task(str(task.id), task.celery_task_id)

        self.assertTrue(result["success"])
        task.refresh_from_db()
        self.assertEqual(task.status, AgentTask.TaskStatus.FAILED)
        self.assertEqual(task.error_message, "Cancelled by user")
        mock_revoke.assert_called_once()
