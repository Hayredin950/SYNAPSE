"""
Tests for AgentTask model.

Phase 5.1 — Agent Framework (Week 13)
"""

import uuid

import pytest
from apps.agents.models import AgentTask
from apps.users.models import User

from django.utils import timezone


@pytest.mark.django_db
class TestAgentTaskModel:
    """Unit tests for the AgentTask model."""

    def _make_user(self, email="agent@test.com"):
        return User.objects.create_user(
            username=email.split("@")[0],
            email=email,
            password="testpass123",
        )

    def test_create_agent_task_defaults(self):
        user = self._make_user()
        task = AgentTask.objects.create(
            user=user,
            task_type="research",
            prompt="Summarise the latest AI trends",
        )
        assert isinstance(task.id, uuid.UUID)
        assert task.status == AgentTask.TaskStatus.PENDING
        assert task.result == {}
        assert task.error_message == ""
        assert task.celery_task_id == ""
        assert task.tokens_used == 0
        assert float(task.cost_usd) == 0.0
        assert task.completed_at is None
        assert task.created_at is not None

    def test_agent_task_str(self):
        user = self._make_user("str@test.com")
        task = AgentTask.objects.create(
            user=user,
            task_type="github",
            prompt="Find trending repos",
        )
        s = str(task)
        assert "github" in s
        assert "pending" in s

    def test_task_status_choices(self):
        choices = [c[0] for c in AgentTask.TaskStatus.choices]
        assert set(choices) == {"pending", "processing", "completed", "failed"}

    def test_status_transition_to_completed(self):
        user = self._make_user("complete@test.com")
        task = AgentTask.objects.create(
            user=user, task_type="arxiv", prompt="Find papers on transformers"
        )
        task.status = AgentTask.TaskStatus.COMPLETED
        task.result = {
            "answer": "Found 5 papers",
            "intermediate_steps": [],
            "execution_time_s": 2.5,
        }
        task.tokens_used = 1500
        task.cost_usd = 0.000112
        task.completed_at = timezone.now()
        task.save()

        refreshed = AgentTask.objects.get(pk=task.pk)
        assert refreshed.status == "completed"
        assert refreshed.result["answer"] == "Found 5 papers"
        assert refreshed.tokens_used == 1500
        assert refreshed.completed_at is not None

    def test_status_transition_to_failed(self):
        user = self._make_user("fail@test.com")
        task = AgentTask.objects.create(
            user=user, task_type="general", prompt="Do something impossible here"
        )
        task.status = AgentTask.TaskStatus.FAILED
        task.error_message = "Timeout exceeded"
        task.completed_at = timezone.now()
        task.save()

        refreshed = AgentTask.objects.get(pk=task.pk)
        assert refreshed.status == "failed"
        assert refreshed.error_message == "Timeout exceeded"

    def test_ordering_newest_first(self):
        user = self._make_user("order@test.com")
        t1 = AgentTask.objects.create(
            user=user, task_type="research", prompt="First task prompt here ok"
        )
        t2 = AgentTask.objects.create(
            user=user, task_type="trends", prompt="Second task prompt here ok"
        )
        tasks = list(AgentTask.objects.filter(user=user))
        assert tasks[0].id == t2.id
        assert tasks[1].id == t1.id

    def test_user_cascade_delete(self):
        user = self._make_user("cascade@test.com")
        AgentTask.objects.create(
            user=user, task_type="github", prompt="Search trending repos on GitHub"
        )
        assert AgentTask.objects.filter(user=user).count() == 1
        user.delete()
        assert AgentTask.objects.filter(task_type="github").count() == 0

    def test_result_json_field_stores_complex_data(self):
        user = self._make_user("json@test.com")
        task = AgentTask.objects.create(
            user=user, task_type="research", prompt="Test JSON storage for research"
        )
        task.result = {
            "answer": "Comprehensive answer.",
            "intermediate_steps": [
                {"tool": "search_knowledge_base", "observation": "Found 3 articles"},
                {"tool": "fetch_arxiv_papers", "observation": "Found 2 papers"},
            ],
            "execution_time_s": 4.2,
        }
        task.save()
        refreshed = AgentTask.objects.get(pk=task.pk)
        assert len(refreshed.result["intermediate_steps"]) == 2
        assert (
            refreshed.result["intermediate_steps"][0]["tool"] == "search_knowledge_base"
        )

    def test_db_table_name(self):
        assert AgentTask._meta.db_table == "agent_tasks"

    def test_related_name_agent_tasks(self):
        user = self._make_user("rel@test.com")
        AgentTask.objects.create(
            user=user, task_type="general", prompt="Task via related name test here"
        )
        assert user.agent_tasks.count() == 1

    def test_celery_task_id_stored(self):
        user = self._make_user("celery@test.com")
        task = AgentTask.objects.create(
            user=user, task_type="research", prompt="Test celery task id field stored"
        )
        fake_celery_id = "celery-abc-123-xyz"
        task.celery_task_id = fake_celery_id
        task.save(update_fields=["celery_task_id"])
        refreshed = AgentTask.objects.get(pk=task.pk)
        assert refreshed.celery_task_id == fake_celery_id
