"""
Tests for AgentTask DRF views.

Phase 5.1 — Agent Framework (Week 13)

Patch notes:
  - execute_agent_task / cancel_agent_task are imported INSIDE view methods,
    so we patch them at their source: apps.agents.tasks.*
  - get_executor is imported inside view methods from ai_engine.agents,
    so we patch: ai_engine.agents.get_executor
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from apps.agents.models import AgentTask
from apps.users.models import User

from rest_framework import status
from rest_framework.test import APIClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_user(email="agentview@test.com", password="testpass123"):
    return User.objects.create_user(
        username=email.split("@")[0], email=email, password=password
    )


def auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


# ---------------------------------------------------------------------------
# AgentTaskListCreateView — GET
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAgentTaskListView:

    def _get_items(self, resp):
        """Extract task list from StandardPagination response {success, data, meta}."""
        body = resp.json()
        return body.get("data", body.get("results", []))

    def _get_total(self, resp):
        """Extract total count from StandardPagination response."""
        body = resp.json()
        return body.get("meta", {}).get(
            "total", body.get("count", len(self._get_items(resp)))
        )

    def test_list_returns_user_tasks_only(self):
        user_a = make_user("a@test.com")
        user_b = make_user("b@test.com")
        AgentTask.objects.create(
            user=user_a, task_type="research", prompt="User A task prompt here ok"
        )
        AgentTask.objects.create(
            user=user_b, task_type="general", prompt="User B task prompt here ok"
        )

        resp = auth_client(user_a).get("/api/v1/agents/tasks/")
        assert resp.status_code == status.HTTP_200_OK
        # StandardPagination returns {success, data, meta}
        assert self._get_total(resp) == 1
        assert len(self._get_items(resp)) == 1

    def test_list_requires_auth(self):
        resp = APIClient().get("/api/v1/agents/tasks/")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_filter_by_status(self):
        user = make_user("filter@test.com")
        AgentTask.objects.create(
            user=user,
            task_type="research",
            prompt="Pending task here for filtering test",
            status="pending",
        )
        AgentTask.objects.create(
            user=user,
            task_type="general",
            prompt="Completed task here for filtering test",
            status="completed",
        )
        resp = auth_client(user).get("/api/v1/agents/tasks/?status=completed")
        assert resp.status_code == status.HTTP_200_OK
        assert self._get_total(resp) == 1

    def test_list_filter_by_task_type(self):
        user = make_user("typefilt@test.com")
        AgentTask.objects.create(
            user=user, task_type="research", prompt="Research task for type filter test"
        )
        AgentTask.objects.create(
            user=user, task_type="arxiv", prompt="Arxiv task for type filter test here"
        )
        resp = auth_client(user).get("/api/v1/agents/tasks/?task_type=arxiv")
        assert resp.status_code == status.HTTP_200_OK
        assert self._get_total(resp) == 1

    def test_list_response_fields(self):
        user = make_user("fields@test.com")
        AgentTask.objects.create(
            user=user, task_type="github", prompt="Check trending GitHub repos today"
        )
        resp = auth_client(user).get("/api/v1/agents/tasks/")
        items = self._get_items(resp)
        assert len(items) > 0
        item = items[0]
        for field in [
            "id",
            "task_type",
            "prompt",
            "status",
            "tokens_used",
            "created_at",
        ]:
            assert field in item, f"Missing field: {field}"


# ---------------------------------------------------------------------------
# AgentTaskListCreateView — POST
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAgentTaskCreateView:

    def test_create_task_success(self):
        user = make_user("create@test.com")
        mock_result = MagicMock()
        mock_result.id = "fake-celery-id-123"

        with patch(
            "apps.agents.tasks.execute_agent_task.delay", return_value=mock_result
        ):
            resp = auth_client(user).post(
                "/api/v1/agents/tasks/",
                {
                    "task_type": "research",
                    "prompt": "What are the latest trends in AI?",
                },
                format="json",
            )
        assert resp.status_code == status.HTTP_201_CREATED
        data = resp.json()
        assert data["task_type"] == "research"
        assert data["status"] == "pending"
        assert AgentTask.objects.filter(user=user).count() == 1

    def test_create_task_invalid_task_type(self):
        user = make_user("invalid@test.com")
        resp = auth_client(user).post(
            "/api/v1/agents/tasks/",
            {"task_type": "not_a_real_type", "prompt": "What are the latest trends?"},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "task_type" in resp.json()

    def test_create_task_prompt_too_short(self):
        user = make_user("short@test.com")
        resp = auth_client(user).post(
            "/api/v1/agents/tasks/",
            {"task_type": "general", "prompt": "too short"},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_task_prompt_too_long(self):
        user = make_user("long@test.com")
        resp = auth_client(user).post(
            "/api/v1/agents/tasks/",
            {"task_type": "general", "prompt": "x" * 4001},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_task_requires_auth(self):
        resp = APIClient().post(
            "/api/v1/agents/tasks/",
            {"task_type": "research", "prompt": "What are the latest trends?"},
            format="json",
        )
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_stores_celery_task_id(self):
        user = make_user("celery_id@test.com")
        mock_result = MagicMock()
        mock_result.id = "celery-xyz-789"

        with patch(
            "apps.agents.tasks.execute_agent_task.delay", return_value=mock_result
        ):
            resp = auth_client(user).post(
                "/api/v1/agents/tasks/",
                {
                    "task_type": "github",
                    "prompt": "Find top starred Python repos today",
                },
                format="json",
            )
        assert resp.status_code == status.HTTP_201_CREATED
        task = AgentTask.objects.get(user=user)
        assert task.celery_task_id == "celery-xyz-789"

    def test_create_all_valid_task_types(self):
        """All documented task_type values must be accepted."""
        user = make_user("alltypes@test.com")
        client = auth_client(user)
        for i, tt in enumerate(["research", "trends", "github", "arxiv", "general"]):
            mock_result = MagicMock()
            mock_result.id = f"celery-{i}"
            with patch(
                "apps.agents.tasks.execute_agent_task.delay", return_value=mock_result
            ):
                resp = client.post(
                    "/api/v1/agents/tasks/",
                    {
                        "task_type": tt,
                        "prompt": f"Valid prompt for task type {tt} number {i}",
                    },
                    format="json",
                )
            assert (
                resp.status_code == status.HTTP_201_CREATED
            ), f"task_type={tt!r} should be valid, got {resp.status_code}"


# ---------------------------------------------------------------------------
# AgentTaskDetailView
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAgentTaskDetailView:

    def test_get_task_detail(self):
        user = make_user("detail@test.com")
        task = AgentTask.objects.create(
            user=user,
            task_type="research",
            prompt="Detailed task prompt for retrieval test",
            status="completed",
            result={
                "answer": "Here is my answer.",
                "intermediate_steps": [],
                "execution_time_s": 1.0,
            },
            tokens_used=300,
        )
        resp = auth_client(user).get(f"/api/v1/agents/tasks/{task.id}/")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["id"] == str(task.id)
        assert data["answer"] == "Here is my answer."
        assert data["tokens_used"] == 300

    def test_get_task_not_found(self):
        user = make_user("notfound@test.com")
        resp = auth_client(user).get(f"/api/v1/agents/tasks/{uuid.uuid4()}/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_cannot_access_another_users_task(self):
        user_a = make_user("owner@test.com")
        user_b = make_user("other@test.com")
        task = AgentTask.objects.create(
            user=user_a,
            task_type="research",
            prompt="Owner task prompt that B should not see at all",
        )
        resp = auth_client(user_b).get(f"/api/v1/agents/tasks/{task.id}/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_detail_includes_intermediate_steps(self):
        user = make_user("steps@test.com")
        task = AgentTask.objects.create(
            user=user,
            task_type="research",
            prompt="Research prompt for intermediate steps test ok",
            result={
                "answer": "Answer text",
                "intermediate_steps": [
                    {"tool": "search_knowledge_base", "observation": "ok"}
                ],
                "execution_time_s": 2.0,
            },
        )
        resp = auth_client(user).get(f"/api/v1/agents/tasks/{task.id}/")
        data = resp.json()
        assert isinstance(data["intermediate_steps"], list)
        assert data["intermediate_steps"][0]["tool"] == "search_knowledge_base"


# ---------------------------------------------------------------------------
# AgentTaskCancelView
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAgentTaskCancelView:

    def test_cancel_pending_task(self):
        user = make_user("cancel@test.com")
        task = AgentTask.objects.create(
            user=user,
            task_type="general",
            prompt="Long running task that needs cancellation now ok",
            status="pending",
            celery_task_id="celery-cancel-123",
        )
        with patch(
            "apps.agents.tasks.cancel_agent_task.delay", return_value=MagicMock()
        ):
            resp = auth_client(user).post(f"/api/v1/agents/tasks/{task.id}/cancel/")
        assert resp.status_code == status.HTTP_200_OK
        assert "Cancellation requested" in resp.json()["message"]

    def test_cannot_cancel_completed_task(self):
        user = make_user("cancel2@test.com")
        task = AgentTask.objects.create(
            user=user,
            task_type="general",
            prompt="Already completed task cannot be cancelled now",
            status="completed",
        )
        resp = auth_client(user).post(f"/api/v1/agents/tasks/{task.id}/cancel/")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_cannot_cancel_failed_task(self):
        user = make_user("cancel3@test.com")
        task = AgentTask.objects.create(
            user=user,
            task_type="general",
            prompt="Already failed task cannot be cancelled now ok",
            status="failed",
        )
        resp = auth_client(user).post(f"/api/v1/agents/tasks/{task.id}/cancel/")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_cancel_not_found(self):
        user = make_user("cancelnf@test.com")
        resp = auth_client(user).post(f"/api/v1/agents/tasks/{uuid.uuid4()}/cancel/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# AgentToolListView
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAgentToolListView:

    def test_list_tools_returns_tools(self):
        mock_executor = MagicMock()
        mock_executor.list_tools.return_value = [
            {
                "name": "search_knowledge_base",
                "description": "Search the knowledge base.",
            },
            {"name": "fetch_articles", "description": "Fetch articles."},
            {"name": "analyze_trends", "description": "Analyze trends."},
            {"name": "search_github", "description": "Search GitHub."},
            {"name": "fetch_arxiv_papers", "description": "Fetch arXiv papers."},
        ]
        user = make_user("tools@test.com")
        with patch("ai_engine.agents.get_executor", return_value=mock_executor):
            resp = auth_client(user).get("/api/v1/agents/tools/")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["count"] == 5
        names = [t["name"] for t in data["tools"]]
        assert "search_knowledge_base" in names
        assert "fetch_articles" in names

    def test_list_tools_graceful_error(self):
        user = make_user("toolserr@test.com")
        with patch(
            "ai_engine.agents.get_executor", side_effect=Exception("Registry error")
        ):
            resp = auth_client(user).get("/api/v1/agents/tools/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["count"] == 0

    def test_list_tools_requires_auth(self):
        resp = APIClient().get("/api/v1/agents/tools/")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


# ---------------------------------------------------------------------------
# Agent Health View
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAgentHealthView:

    def test_health_ok(self):
        mock_executor = MagicMock()
        mock_executor.health.return_value = {
            "status": "ok",
            "tools_registered": 9,
            "tool_names": ["search_knowledge_base", "fetch_articles"],
            "model": "gemini-1.5-flash-latest",
            "max_iterations": 10,
            "max_execution_time_s": 300,
        }
        user = make_user("health@test.com")
        with patch("ai_engine.agents.get_executor", return_value=mock_executor):
            resp = auth_client(user).get("/api/v1/agents/health/")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["status"] == "ok"
        assert data["tools_registered"] == 9

    def test_health_error_returns_503(self):
        user = make_user("health2@test.com")
        with patch(
            "ai_engine.agents.get_executor", side_effect=Exception("LLM unavailable")
        ):
            resp = auth_client(user).get("/api/v1/agents/health/")
        assert resp.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert resp.json()["status"] == "error"

    def test_health_requires_auth(self):
        resp = APIClient().get("/api/v1/agents/health/")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED
