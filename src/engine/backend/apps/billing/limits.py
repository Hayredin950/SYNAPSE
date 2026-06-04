"""
backend.apps.billing.limits
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Plan limit enforcement — check resource usage against subscription plan caps.

TASK-003-B5

Usage:
    from apps.billing.limits import check_plan_limit, user_has_feature

    # Raises PermissionDenied with plan_limit_exceeded error_code if exceeded
    check_plan_limit(request.user, "ai_queries")

    # Returns bool
    if not user_has_feature(request.user, "api_access"):
        raise PermissionDenied(...)
"""

from __future__ import annotations

import structlog

from django.core.exceptions import PermissionDenied

logger = structlog.get_logger(__name__)


# ── Plan limits table ──────────────────────────────────────────────────────────

PLAN_LIMITS = {
    "free": {
        "ai_queries": 50,  # per month
        "agent_runs": 5,  # per month
        "automations": 5,
        "documents": 10,
        "bookmarks": 100,
    },
    "pro": {
        "ai_queries": -1,  # unlimited
        "agent_runs": -1,
        "automations": -1,
        "documents": -1,
        "bookmarks": -1,
    },
    "enterprise": {
        "ai_queries": -1,
        "agent_runs": -1,
        "automations": -1,
        "documents": -1,
        "bookmarks": -1,
    },
}

# Features gated by plan
PLAN_FEATURES = {
    "free": {
        "semantic_search": False,
        "api_access": False,
        "google_drive": False,
        "private_repos": False,
        "teams": False,
        "custom_ai": False,
        "audit_logs": False,
        "sso": False,
        "advanced_analytics": False,
    },
    "pro": {
        "semantic_search": True,
        "api_access": True,
        "google_drive": True,
        "private_repos": True,
        "teams": False,
        "custom_ai": False,
        "audit_logs": False,
        "sso": False,
        "advanced_analytics": True,
    },
    "enterprise": {
        "semantic_search": True,
        "api_access": True,
        "google_drive": True,
        "private_repos": True,
        "teams": True,
        "custom_ai": True,
        "audit_logs": True,
        "sso": True,
        "advanced_analytics": True,
    },
}


# ── Public helpers ─────────────────────────────────────────────────────────────


def get_user_plan(user) -> str:
    """Return the user's current plan string (free/pro/enterprise)."""
    try:
        sub = user.subscription
        if sub.is_active and sub.plan in PLAN_LIMITS:
            return sub.plan
    except Exception:
        pass
    return "free"


def get_plan_limit(plan: str, resource: str) -> int:
    """Return the numeric limit for a resource on a given plan. -1 = unlimited."""
    return PLAN_LIMITS.get(plan, PLAN_LIMITS["free"]).get(resource, 0)


def user_has_feature(user, feature: str) -> bool:
    """
    Return True if the user's plan includes the given feature.

    Example:
        user_has_feature(user, "google_drive")  → True if pro/enterprise
    """
    plan = get_user_plan(user)
    return PLAN_FEATURES.get(plan, PLAN_FEATURES["free"]).get(feature, False)


def check_plan_limit(user, resource: str, current_usage: int | None = None) -> None:
    """
    Check whether the user has exceeded their plan limit for a resource.

    Raises PermissionDenied (with error_code='plan_limit_exceeded') if over limit.

    If current_usage is None, the function attempts to auto-count from the DB.
    Otherwise pass the current count explicitly for performance.
    """
    plan = get_user_plan(user)
    limit = get_plan_limit(plan, resource)

    if limit == -1:
        # Unlimited — always pass
        return

    if current_usage is None:
        current_usage = _count_usage(user, resource)

    if current_usage >= limit:
        logger.warning(
            "plan_limit_exceeded",
            user=user.email,
            plan=plan,
            resource=resource,
            usage=current_usage,
            limit=limit,
        )
        exc = PermissionDenied(
            f"You've reached your {plan} plan limit for {resource} "
            f"({current_usage}/{limit}). Upgrade to Pro for unlimited access."
        )
        exc.error_code = "plan_limit_exceeded"  # type: ignore[attr-defined]
        exc.resource = resource  # type: ignore[attr-defined]
        exc.plan = plan  # type: ignore[attr-defined]
        exc.limit = limit  # type: ignore[attr-defined]
        exc.usage = current_usage  # type: ignore[attr-defined]
        raise exc


def _count_usage(user, resource: str) -> int:
    """Auto-count resource usage from the DB for current billing period."""
    from datetime import timedelta

    from django.utils import timezone

    # Use start of current calendar month as period start
    now = timezone.now()
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    if resource == "ai_queries":
        try:
            from apps.core.models import Conversation

            return Conversation.objects.filter(user=user, created_at__gte=start).count()
        except Exception:
            return 0

    if resource == "agent_runs":
        try:
            from apps.agents.models import AgentTask

            return AgentTask.objects.filter(user=user, created_at__gte=start).count()
        except Exception:
            return 0

    if resource == "automations":
        try:
            from apps.automation.models import Workflow

            return Workflow.objects.filter(user=user).count()
        except Exception:
            return 0

    if resource == "documents":
        try:
            from apps.documents.models import GeneratedDocument

            return GeneratedDocument.objects.filter(
                user=user, created_at__gte=start
            ).count()
        except Exception:
            return 0

    if resource == "bookmarks":
        try:
            from apps.core.models import Bookmark

            return Bookmark.objects.filter(user=user).count()
        except Exception:
            return 0

    return 0


# ── Aliases for backwards-compat / alternate naming conventions ───────────────


def get_plan_limits(plan: str) -> dict:
    """Return the full limits dict for a plan. Falls back to free for unknown plans."""
    return dict(PLAN_LIMITS.get(plan, PLAN_LIMITS["free"]))


def check_limit(plan: str, resource: str, current_usage: int) -> bool:
    """
    Return True if current_usage is within the plan limit for resource, False if exceeded.

    Unlike check_plan_limit (which raises), this returns a bool for simple gating.
    -1 limit means unlimited → always True.
    """
    limit = get_plan_limit(plan, resource)
    if limit == -1:
        return True
    return current_usage < limit


# ── DRF-friendly exception handler helper ─────────────────────────────────────


def plan_limit_response(exc) -> dict:
    """
    Convert a PermissionDenied(error_code='plan_limit_exceeded') into a
    JSON-serialisable dict for DRF responses.
    """
    return {
        "error": str(exc),
        "error_code": getattr(exc, "error_code", "plan_limit_exceeded"),
        "resource": getattr(exc, "resource", None),
        "plan": getattr(exc, "plan", None),
        "limit": getattr(exc, "limit", None),
        "usage": getattr(exc, "usage", None),
        "upgrade_url": "/billing",
    }
