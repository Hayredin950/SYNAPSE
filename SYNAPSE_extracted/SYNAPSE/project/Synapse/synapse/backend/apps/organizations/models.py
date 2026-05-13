"""
backend.apps.organizations.models
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Team Workspaces & Organizations — TASK-006

Models:
  Organization  — a named workspace (free or team plan)
  Membership    — links User ↔ Organization with a role
  OrganizationInvite — pending email invites

Design decisions:
  - An Organization is owned by exactly one User (owner).
  - Members can have role: owner / admin / member / viewer.
  - Free plan: max 1 org, max 5 members.
  - Pro plan:  max 3 orgs, max 25 members.
  - Enterprise: unlimited.
  - Org slug is URL-safe identifier (unique).
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.utils.text import slugify

# ── Constants ─────────────────────────────────────────────────────────────────


class OrgRole(models.TextChoices):
    OWNER = "owner", "Owner"
    ADMIN = "admin", "Admin"
    MEMBER = "member", "Member"
    VIEWER = "viewer", "Viewer"


class OrgPlan(models.TextChoices):
    FREE = "free", "Free"
    PRO = "pro", "Pro"
    ENTERPRISE = "enterprise", "Enterprise"


# ── Organization ──────────────────────────────────────────────────────────────


class Organization(models.Model):
    """A team workspace that can contain multiple members."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=110, unique=True, db_index=True)
    description = models.TextField(blank=True, max_length=500)
    logo_url = models.URLField(blank=True, max_length=500)
    website = models.URLField(blank=True, max_length=500)
    plan = models.CharField(
        max_length=20, choices=OrgPlan.choices, default=OrgPlan.FREE
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="owned_organizations",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Plan limits
    MAX_MEMBERS = {"free": 5, "pro": 25, "enterprise": -1}
    MAX_ORGS = {"free": 1, "pro": 3, "enterprise": -1}

    class Meta:
        db_table = "organizations"
        verbose_name = "Organization"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.name} ({self.slug})"

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            n = 1
            while Organization.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{n}"
                n += 1
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def member_count(self) -> int:
        return self.memberships.filter(is_active=True).count()

    @property
    def max_members(self) -> int:
        return self.MAX_MEMBERS.get(self.plan, 5)

    @property
    def is_full(self) -> bool:
        limit = self.max_members
        if limit == -1:
            return False
        return self.member_count >= limit

    def user_role(self, user) -> str | None:
        """Return the role of `user` in this org, or None if not a member."""
        try:
            m = self.memberships.get(user=user, is_active=True)
            return m.role
        except Membership.DoesNotExist:
            return None

    def is_member(self, user) -> bool:
        return self.memberships.filter(user=user, is_active=True).exists()

    def is_admin_or_owner(self, user) -> bool:
        role = self.user_role(user)
        return role in (OrgRole.OWNER, OrgRole.ADMIN)


# ── OrgAuditLog ───────────────────────────────────────────────────────────────


class OrgAuditLog(models.Model):
    """
    TASK-006-B5: Immutable audit trail for organisation changes.
    Records: member_added, member_removed, role_changed, invite_sent,
             invite_cancelled, invite_accepted, settings_changed, org_created, org_deleted.
    """

    class Action(models.TextChoices):
        ORG_CREATED = "org_created", "Org Created"
        ORG_DELETED = "org_deleted", "Org Deleted"
        SETTINGS_CHANGED = "settings_changed", "Settings Changed"
        MEMBER_ADDED = "member_added", "Member Added"
        MEMBER_REMOVED = "member_removed", "Member Removed"
        ROLE_CHANGED = "role_changed", "Role Changed"
        INVITE_SENT = "invite_sent", "Invite Sent"
        INVITE_CANCELLED = "invite_cancelled", "Invite Cancelled"
        INVITE_ACCEPTED = "invite_accepted", "Invite Accepted"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="audit_logs"
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="org_audit_actions",
    )
    action = models.CharField(max_length=30, choices=Action.choices, db_index=True)
    # Human-readable label for the resource affected (e.g. email, username)
    resource = models.CharField(max_length=255, blank=True)
    # Arbitrary JSON payload for extra context
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "org_audit_logs"
        verbose_name = "Org Audit Log"
        ordering = ["-timestamp"]

    def __str__(self) -> str:
        actor = self.actor.email if self.actor else "system"
        return f"[{self.organization.slug}] {actor} → {self.action} ({self.resource})"


# ── Membership ────────────────────────────────────────────────────────────────


class Membership(models.Model):
    """Links a User to an Organization with a specific role."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="memberships"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="org_memberships",
    )
    role = models.CharField(
        max_length=20, choices=OrgRole.choices, default=OrgRole.MEMBER
    )
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "organization_memberships"
        unique_together = [("organization", "user")]
        verbose_name = "Membership"
        ordering = ["joined_at"]

    def __str__(self) -> str:
        return f"{self.user.email} → {self.organization.name} ({self.role})"


# ── OrganizationInvite ────────────────────────────────────────────────────────


class OrganizationInvite(models.Model):
    """
    A pending invite to join an organization.
    Sent to an email address; accepted by the invited user.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="invites"
    )
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_org_invites",
    )
    email = models.EmailField(db_index=True)
    role = models.CharField(
        max_length=20, choices=OrgRole.choices, default=OrgRole.MEMBER
    )
    token = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    is_accepted = models.BooleanField(default=False)
    accepted_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "organization_invites"
        verbose_name = "Organization Invite"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Invite → {self.email} to {self.organization.name}"

    @property
    def is_expired(self) -> bool:
        if not self.expires_at:
            return False
        from django.utils import timezone

        return timezone.now() > self.expires_at
