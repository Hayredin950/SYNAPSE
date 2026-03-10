"""
URL configuration for the Automation app.

  GET/POST   /api/v1/automation/workflows/
  GET/PUT/PATCH/DELETE /api/v1/automation/workflows/<id>/
  POST       /api/v1/automation/workflows/<id>/trigger/
  POST       /api/v1/automation/workflows/<id>/toggle/
  GET        /api/v1/automation/workflows/<id>/runs/
  GET        /api/v1/automation/runs/<id>/
  GET        /api/v1/automation/runs/<id>/status/   ← live polling / SSE
  POST       /api/v1/automation/events/trigger/     ← event dispatch
"""

from django.urls import path

from . import views
from .views import (
    WorkflowListCreateView,
    WorkflowRetrieveUpdateDestroyView,
    WorkflowRunDetailView,
    WorkflowRunListView,
    WorkflowRunStatusView,
    WorkflowToggleView,
    WorkflowTriggerView,
    action_schemas_view,
    clone_template_view,
    list_schedule_view,
    list_templates_view,
    toggle_schedule_view,
    trigger_event_view,
    workflow_analytics_view,
)

urlpatterns = [
    # Workflow CRUD
    path("workflows/", WorkflowListCreateView.as_view(), name="workflow-list-create"),
    path(
        "workflows/<uuid:pk>/",
        WorkflowRetrieveUpdateDestroyView.as_view(),
        name="workflow-detail",
    ),
    # Workflow actions
    path(
        "workflows/<uuid:pk>/trigger/",
        WorkflowTriggerView.as_view(),
        name="workflow-trigger",
    ),
    path(
        "workflows/<uuid:pk>/toggle/",
        WorkflowToggleView.as_view(),
        name="workflow-toggle",
    ),
    # Run history
    path(
        "workflows/<uuid:pk>/runs/", WorkflowRunListView.as_view(), name="workflow-runs"
    ),
    path("runs/<uuid:pk>/", WorkflowRunDetailView.as_view(), name="run-detail"),
    # Live run status (SSE / polling)
    path("runs/<uuid:pk>/status/", WorkflowRunStatusView.as_view(), name="run-status"),
    # Internal event trigger dispatch
    path("events/trigger/", trigger_event_view, name="event-trigger"),
    # Action parameter schemas for the UI editor
    path("action-schemas/", action_schemas_view, name="action-schemas"),
    # Workflow templates
    path("templates/", list_templates_view, name="template-list"),
    path(
        "templates/<str:template_id>/clone/", clone_template_view, name="template-clone"
    ),
    # Scheduled task management
    path("schedule/", list_schedule_view, name="schedule-list"),
    path("schedule/<uuid:pk>/toggle/", toggle_schedule_view, name="schedule-toggle"),
    # Analytics
    path("analytics/", workflow_analytics_view, name="workflow-analytics"),
    # TASK-604-B2: Automation Marketplace
    path("marketplace/", views.MarketplaceListView.as_view(), name="marketplace-list"),
    path(
        "marketplace/<uuid:pk>/",
        views.MarketplaceDetailView.as_view(),
        name="marketplace-detail",
    ),
    path(
        "marketplace/<uuid:pk>/install/",
        views.MarketplaceInstallView.as_view(),
        name="marketplace-install",
    ),
    path(
        "marketplace/<uuid:pk>/publish/",
        views.MarketplacePublishView.as_view(),
        name="marketplace-publish",
    ),
    path(
        "marketplace/<uuid:pk>/upvote/",
        views.MarketplaceUpvoteView.as_view(),
        name="marketplace-upvote",
    ),
]
