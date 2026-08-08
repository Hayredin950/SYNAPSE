"""
backend.apps.agents.tests.test_agent_e2e
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
End-to-end integration tests for the full agent task flow.

Phase 5.4 — Agent UI (Week 16)

Covers:
  - Creating an agent task via POST /api/v1/agents/tasks/
  - Polling task status via GET /api/v1/agents/tasks/{id}/
  - Cancelling a pending task via POST /api/v1/agents/tasks/{id}/cancel/
  - SSE stream endpoint returns correct content-type
  - Tool list endpoint returns registered tools
  - Health check endpoint
  - Cost and token fields are present and correct types
  - Task history filtering by status

Patch notes:
  - execute_agent_task / cancel_agent_task are imported locally inside view
    methods, so patch at source: apps.agents.tasks.*
  - get_executor is imported locally inside view methods from ai_engine.agents,
    so patch at: ai_engine.agents.get_executor
  - StandardPagination returns {success, data, meta} — tests use data["data"]
  - SSE endpoint bypasses DRF content negotiation; test uses Django test client
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

from apps.agents.models import AgentTask
from apps.users.models import User

from django.test import TestCase as DjangoTestCase
from rest_framework import status
from rest_framework.test import APITestCase


class AgentTaskE2ETest(APITestCase):
    """Full lifecycle: create → poll → complete → history."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="agentuser",
            email="agentuser@test.com",
            password="testpass123",
        )
        self.client.force_authenticate(user=self.user)

    # ── create task ───────────────────────────────────────────────────────────

    @patch("apps.agents.tasks.execute_agent_task")
    def test_create_task_returns_201(self, mock_celery):
        """POST /agents/tasks/ creates an AgentTask and queues it."""
        mock_result = MagicMock()
        mock_result.id = str(uuid.uuid4())
        mock_celery.delay.return_value = mock_result

        payload = {
            "task_type": "general",
            "prompt": "Summarise the latest AI news for me.",
        }
        response = self.client.post("/api/v1/agents/tasks/", payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertIn("id", data)
        self.assertEqual(data["task_type"], "general")
        self.assertEqual(data["status"], "pending")
        self.assertIn("cost_usd", data)
        self.assertIn("tokens_used", data)

    def test_create_task_prompt_too_short(self):
        """Prompt shorter than 10 chars should be rejected with 400."""
        payload = {"task_type": "general", "prompt": "short"}
        response = self.client.post("/api/v1/agents/tasks/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_task_invalid_type(self):
        """Unknown task_type should be rejected with 400."""
        payload = {
            "task_type": "unknown_type",
            "prompt": "This is a valid long enough prompt.",
        }
        response = self.client.post("/api/v1/agents/tasks/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_task_requires_auth(self):
        """Unauthenticated requests should get 401."""
        self.client.force_authenticate(user=None)
        payload = {
            "task_type": "general",
            "prompt": "This is a valid long enough prompt.",
        }
        response = self.client.post("/api/v1/agents/tasks/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # ── poll task detail ───────────────────────────────────────────────────────

    def test_get_task_detail(self):
        """GET /agents/tasks/{id}/ returns full task detail."""
        task = AgentTask.objects.create(
            user=self.user,
            task_type="research",
            prompt="What are the latest developments in quantum computing?",
            status=AgentTask.TaskStatus.COMPLETED,
            result={
                "answer": "Quantum computing advances rapidly.",
                "tokens_used": 512,
            },
            tokens_used=512,
            cost_usd="0.000768",
        )
        response = self.client.get(f"/api/v1/agents/tasks/{task.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["id"], str(task.id))
        self.assertEqual(data["status"], "completed")
        self.assertEqual(data["tokens_used"], 512)
        self.assertIn("answer", data)

    def test_get_task_not_found(self):
        """GET for non-existent task returns 404."""
        fake_id = uuid.uuid4()
        response = self.client.get(f"/api/v1/agents/tasks/{fake_id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cannot_access_other_users_task(self):
        """User A cannot retrieve User B's task."""
        other = User.objects.create_user(
            username="other", email="other@test.com", password="pass"
        )
        task = AgentTask.objects.create(
            user=other,
            task_type="general",
            prompt="This belongs to another user entirely.",
            status=AgentTask.TaskStatus.PENDING,
        )
        response = self.client.get(f"/api/v1/agents/tasks/{task.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ── list + filter ──────────────────────────────────────────────────────────

    def test_list_tasks_returns_only_own(self):
        """GET /agents/tasks/ returns only the authenticated user's tasks.
        StandardPagination returns {success, data, meta} format.
        """
        AgentTask.objects.create(
            user=self.user, task_type="general", prompt="My task, long enough."
        )
        other = User.objects.create_user(
            username="stranger", email="s@test.com", password="pass"
        )
        AgentTask.objects.create(
            user=other, task_type="general", prompt="Stranger task, long enough."
        )

        response = self.client.get("/api/v1/agents/tasks/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        # StandardPagination wraps items in "data" key
        items = body.get("data", body.get("results", []))
        task_ids = [t["id"] for t in items]
        # Only self.user's tasks should be returned
        for task_id in task_ids:
            self.assertTrue(
                AgentTask.objects.filter(id=task_id, user=self.user).exists()
            )
        # Stranger's task must not appear
        stranger_tasks = AgentTask.objects.filter(user=other)
        stranger_ids = [str(t.id) for t in stranger_tasks]
        for sid in stranger_ids:
            self.assertNotIn(sid, task_ids)

    def test_filter_tasks_by_status(self):
        """?status=completed filter returns only completed tasks."""
        AgentTask.objects.create(
            user=self.user,
            task_type="general",
            prompt="Pending task, long enough text.",
            status="pending",
        )
        AgentTask.objects.create(
            user=self.user,
            task_type="research",
            prompt="Completed task, long enough text.",
            status="completed",
        )

        response = self.client.get("/api/v1/agents/tasks/?status=completed")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        items = body.get("data", body.get("results", []))
        self.assertGreaterEqual(len(items), 1)
        for task in items:
            self.assertEqual(task["status"], "completed")

    # ── cancel ─────────────────────────────────────────────────────────────────

    @patch("apps.agents.tasks.cancel_agent_task")
    def test_cancel_pending_task(self, mock_cancel):
        """POST /agents/tasks/{id}/cancel/ cancels a pending task."""
        mock_cancel.delay.return_value = MagicMock()
        task = AgentTask.objects.create(
            user=self.user,
            task_type="general",
            prompt="A cancelable task with sufficient length.",
            status=AgentTask.TaskStatus.PENDING,
            celery_task_id=str(uuid.uuid4()),
        )
        response = self.client.post(f"/api/v1/agents/tasks/{task.id}/cancel/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("message", response.json())

    def test_cancel_completed_task_fails(self):
        """Cannot cancel an already-completed task."""
        task = AgentTask.objects.create(
            user=self.user,
            task_type="general",
            prompt="A completed task with sufficient length.",
            status=AgentTask.TaskStatus.COMPLETED,
        )
        response = self.client.post(f"/api/v1/agents/tasks/{task.id}/cancel/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # ── SSE stream ─────────────────────────────────────────────────────────────

    def test_sse_stream_content_type(self):
        """GET /agents/tasks/{id}/stream/ returns text/event-stream content type.
        The SSE view is a plain Django view (bypasses DRF content negotiation).
        Uses JWT Bearer token for authentication.
        """
        from rest_framework_simplejwt.tokens import AccessToken

        from django.test import Client as DjangoClient

        task = AgentTask.objects.create(
            user=self.user,
            task_type="general",
            prompt="Stream this task result with enough characters.",
            status=AgentTask.TaskStatus.COMPLETED,
            result={"answer": "Done."},
            tokens_used=100,
        )
        token = str(AccessToken.for_user(self.user))
        client = DjangoClient()
        response = client.get(
            f"/api/v1/agents/tasks/{task.id}/stream/",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/event-stream", response.get("Content-Type", ""))

    def test_sse_stream_not_found(self):
        """SSE for non-existent task returns 404 (authenticated but task doesn't exist)."""
        from rest_framework_simplejwt.tokens import AccessToken

        from django.test import Client as DjangoClient

        fake_id = uuid.uuid4()
        token = str(AccessToken.for_user(self.user))
        client = DjangoClient()
        response = client.get(
            f"/api/v1/agents/tasks/{fake_id}/stream/",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 404)

    # ── tools ──────────────────────────────────────────────────────────────────

    @patch("ai_engine.agents.get_executor")
    def test_tools_list(self, mock_get_executor):
        """GET /agents/tools/ returns tool list."""
        mock_executor = MagicMock()
        mock_executor.list_tools.return_value = [
            {
                "name": "search_knowledge_base",
                "description": "Searches the knowledge base.",
            },
            {"name": "fetch_articles", "description": "Fetches articles."},
        ]
        mock_get_executor.return_value = mock_executor

        response = self.client.get("/api/v1/agents/tools/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("tools", data)
        self.assertIn("count", data)

    # ── health ─────────────────────────────────────────────────────────────────

    @patch("ai_engine.agents.get_executor")
    def test_health_check(self, mock_get_executor):
        """GET /agents/health/ returns status ok."""
        mock_executor = MagicMock()
        mock_executor.health.return_value = {"status": "ok", "tools": 10}
        mock_get_executor.return_value = mock_executor

        response = self.client.get("/api/v1/agents/health/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["status"], "ok")

    # ── cost & token fields ────────────────────────────────────────────────────

    def test_task_has_cost_and_token_fields(self):
        """AgentTask model stores cost_usd and tokens_used correctly."""
        task = AgentTask.objects.create(
            user=self.user,
            task_type="trends",
            prompt="Analyze current trends in open source software development.",
            status=AgentTask.TaskStatus.COMPLETED,
            tokens_used=1234,
            cost_usd="0.001851",
        )
        response = self.client.get(f"/api/v1/agents/tasks/{task.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["tokens_used"], 1234)
        self.assertIn("cost_usd", data)
        self.assertAlmostEqual(float(data["cost_usd"]), 0.001851, places=5)
