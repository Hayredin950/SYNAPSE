"""
TASK-505-B1/B2: Audit Log system.

AuditLog model records all sensitive actions:
  - Authentication events (login, logout, MFA)
  - API key creation/revocation
  - Billing/subscription changes
  - Organization membership changes
  - Document generation/access
  - AI query actions

Decorator `@audit_action(action)` logs any view/function call.
"""

from __future__ import annotations

import functools
import logging

from django.conf import settings
from django.db import models

logger = logging.getLogger(__name__)


# ── Model ─────────────────────────────────────────────────────────────────────


class AuditLog(models.Model):
    """Immutable record of a sensitive action performed by a user."""

    class Action(models.TextChoices):
        # Auth
        LOGIN = "login", "Login"
        LOGOUT = "logout", "Logout"
        LOGIN_FAILED = "login_failed", "Login Failed"
        MFA_ENABLED = "mfa_enabled", "MFA Enabled"
        MFA_DISABLED = "mfa_disabled", "MFA Disabled"
        PASSWORD_CHANGED = "password_changed", "Password Changed"
        # API Keys
        API_KEY_CREATED = "api_key_created", "API Key Created"
        API_KEY_REVOKED = "api_key_revoked", "API Key Revoked"
        # Billing
        SUBSCRIPTION_CREATED = "subscription_created", "Subscription Created"
        SUBSCRIPTION_CANCELLED = "subscription_cancelled", "Subscription Cancelled"
        PAYMENT_FAILED = "payment_failed", "Payment Failed"
        # Organizations
        ORG_CREATED = "org_created", "Org Created"
        ORG_MEMBER_ADDED = "org_member_added", "Org Member Added"
        ORG_MEMBER_REMOVED = "org_member_removed", "Org Member Removed"
        # Documents
        DOCUMENT_GENERATED = "document_generated", "Document Generated"
        DOCUMENT_DELETED = "document_deleted", "Document Deleted"
        # AI
        AI_QUERY = "ai_query", "AI Query"
        AGENT_TASK_CREATED = "agent_task_created", "Agent Task Created"
        # Data
        DATA_EXPORTED = "data_exported", "Data Exported"
        ACCOUNT_DELETED = "account_deleted", "Account Deleted"
        # Generic
        OTHER = "other", "Other"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    action = models.CharField(max_length=50, choices=Action.choices, db_index=True)
    target_id = models.CharField(max_length=200, blank=True, db_index=True)
    target_type = models.CharField(max_length=100, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    metadata = models.JSONField(default=dict)  # extra context (e.g. key name, org slug)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "audit_logs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"], name="al_user_created_idx"),
            models.Index(
                fields=["action", "-created_at"], name="al_action_created_idx"
            ),
        ]

    def __str__(self):
        user_str = str(self.user_id) if self.user_id else "anonymous"
        return f"[{self.created_at.date()}] {user_str} → {self.action}"


# ── Helpers ────────────────────────────────────────────────────────────────────


def get_client_ip(request) -> str | None:
    """Extract real client IP from request (handles proxies)."""
    x_forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded:
        return x_forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def log_action(
    action: str,
    user=None,
    request=None,
    target_id: str = "",
    target_type: str = "",
    metadata: dict | None = None,
) -> AuditLog | None:
    """
    Create an AuditLog entry.

    Usage:
        log_action('api_key_created', user=request.user, request=request,
                   target_id=key.key_prefix, metadata={'name': key.name})
    """
    try:
        ip = get_client_ip(request) if request else None
        user_agent = request.META.get("HTTP_USER_AGENT", "")[:1000] if request else ""

        return AuditLog.objects.create(
            user=user,
            action=action,
            target_id=target_id,
            target_type=target_type,
            ip_address=ip,
            user_agent=user_agent,
            metadata=metadata or {},
        )
    except Exception as exc:
        logger.error("Failed to create AuditLog: %s", exc)
        return None


# ── Decorator ─────────────────────────────────────────────────────────────────


def audit_action(action: str, target_type: str = "", get_target_id=None):
    """
    TASK-505-B2: Decorator for DRF views / Django views.

    Extracts request from kwargs first (DRF passes it as a kwarg in some cases),
    then falls back to positional arg inspection using isinstance checks rather
    than fragile index assumptions.

    Usage:
        @audit_action('api_key_created', target_type='APIKey')
        def post(self, request):
            ...
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            from django.http import HttpRequest  # noqa: PLC0415
            from rest_framework.request import Request as DRFRequest  # noqa: PLC0415

            # Robust request extraction: check kwargs first, then all positional args
            request = kwargs.get("request", None)
            if request is None:
                for arg in args:
                    if isinstance(arg, (DRFRequest, HttpRequest)):
                        request = arg
                        break

            user = getattr(request, "user", None)

            result = func(*args, **kwargs)

            # Log after successful execution
            target_id_val = ""
            if get_target_id:
                try:
                    target_id_val = str(get_target_id(result))
                except Exception:
                    pass

            log_action(
                action=action,
                user=user if user and user.is_authenticated else None,
                request=request,
                target_type=target_type,
                target_id=target_id_val,
            )
            return result

        return wrapper

    return decorator
