"""
URL routes for Team Workspaces & Organizations — TASK-006
"""

from django.urls import path

from .views import (
    AuditLogListView,
    InviteAcceptView,
    InviteDeleteView,
    InviteListCreateView,
    MemberDetailView,
    MemberListView,
    OrganizationDetailView,
    OrganizationListCreateView,
)

urlpatterns = [
    # Org CRUD
    path("", OrganizationListCreateView.as_view(), name="org-list-create"),
    path("<uuid:pk>/", OrganizationDetailView.as_view(), name="org-detail"),
    # Member management
    path("<uuid:pk>/members/", MemberListView.as_view(), name="org-member-list"),
    path(
        "<uuid:pk>/members/<uuid:user_id>/",
        MemberDetailView.as_view(),
        name="org-member-detail",
    ),
    # Invites
    path("<uuid:pk>/invites/", InviteListCreateView.as_view(), name="org-invite-list"),
    path(
        "<uuid:pk>/invites/<uuid:invite_id>/",
        InviteDeleteView.as_view(),
        name="org-invite-delete",
    ),
    # Accept invite (token-based, no org ID in URL)
    path(
        "invites/<uuid:token>/accept/",
        InviteAcceptView.as_view(),
        name="org-invite-accept",
    ),
    # Audit log (TASK-006-B5)
    path("<uuid:pk>/audit-logs/", AuditLogListView.as_view(), name="org-audit-log"),
]
