"""
backend.apps.organizations.permissions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
DRF permission classes for RBAC on Organization resources — TASK-006-B3

Usage:
    class MyView(APIView):
        permission_classes = [IsAuthenticated, IsOrgMember]
"""

from __future__ import annotations

from rest_framework.permissions import BasePermission

from .models import OrgRole


def get_user_org_role(user, org) -> str | None:
    """Return the user's role in `org`, or None if not an active member."""
    return org.user_role(user)


class IsOrgMember(BasePermission):
    """
    Allow access only to active members of the organization (any role).
    Expects the view to set `self.org` or to pass `org` via kwargs.
    """

    message = "You must be a member of this organization."

    def has_object_permission(self, request, view, obj):
        return obj.is_member(request.user)


class IsOrgAdminOrOwner(BasePermission):
    """Allow access only to admins and owners."""

    message = "Admin or owner role required."

    def has_object_permission(self, request, view, obj):
        return obj.is_admin_or_owner(request.user)


class IsOrgOwner(BasePermission):
    """Allow access only to the organization owner."""

    message = "Only the organization owner can perform this action."

    def has_object_permission(self, request, view, obj):
        return obj.owner == request.user
