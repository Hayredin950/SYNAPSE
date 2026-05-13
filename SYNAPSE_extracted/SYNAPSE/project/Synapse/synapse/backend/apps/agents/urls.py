"""
backend.apps.agents.urls
~~~~~~~~~~~~~~~~~~~~~~~~
URL routing for the Agentic AI framework.

Phase 5.1 — Agent Framework (Week 13)

Mounted at: /api/v1/agents/
"""

from django.urls import path

from . import views

urlpatterns = [
    # Task CRUD
    path(
        "tasks/", views.AgentTaskListCreateView.as_view(), name="agent-task-list-create"
    ),
    path(
        "tasks/<uuid:task_id>/",
        views.AgentTaskDetailView.as_view(),
        name="agent-task-detail",
    ),
    path(
        "tasks/<uuid:task_id>/cancel/",
        views.AgentTaskCancelView.as_view(),
        name="agent-task-cancel",
    ),
    # SSE real-time streaming (Phase 5.4)
    path(
        "tasks/<uuid:task_id>/stream/",
        views.agent_task_stream,
        name="agent-task-stream",
    ),
    # Tool registry
    path("tools/", views.AgentToolListView.as_view(), name="agent-tool-list"),
    # Health
    path("health/", views.agent_health, name="agent-health"),
    # ── TASK-306-B2: Prompt Library ──────────────────────────────────────────
    path("prompts/", views.PromptListCreateView.as_view(), name="prompt-list-create"),
    path("prompts/my/", views.MyPromptsView.as_view(), name="prompt-my"),
    path("prompts/<uuid:pk>/", views.PromptDetailView.as_view(), name="prompt-detail"),
    path("prompts/<uuid:pk>/use/", views.PromptUseView.as_view(), name="prompt-use"),
    path(
        "prompts/<uuid:pk>/upvote/",
        views.PromptUpvoteView.as_view(),
        name="prompt-upvote",
    ),
    # ── TASK-601-B3: Research session endpoints ───────────────────────────────
    path(
        "research/",
        views.ResearchSessionListCreateView.as_view(),
        name="research-list-create",
    ),
    path(
        "research/<uuid:pk>/",
        views.ResearchSessionDetailView.as_view(),
        name="research-detail",
    ),
]
