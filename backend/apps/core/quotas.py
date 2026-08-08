"""
backend.apps.core.quotas
~~~~~~~~~~~~~~~~~~~~~~~~~
Universal per-user quota enforcement.

SYNAPSE is free to use — there are no paid plans. Quotas exist purely to keep a
single user (or a runaway script) from exhausting the shared upstream AI
provider quota for everybody else.

Two ceilings apply to every metered resource:

  * a DAILY cap  — stops burst exhaustion (one user draining the day's budget)
  * a MONTHLY cap — stops slow-drip exhaustion over the billing period

The daily cap is the important one. Agent runs fan out into a ReAct loop of up
to ``MAX_ITERATIONS`` LLM calls each, so a handful of unthrottled users can
burn a day's worth of upstream free-tier requests in minutes.

Usage:
    from apps.core.quotas import check_quota, user_has_feature

    # Raises PermissionDenied with error_code='quota_exceeded' if over limit
    check_quota(request.user, "agent_runs")

    if not user_has_feature(user, "api_access"):
        raise PermissionDenied(...)
"""

from __future__ import annotations

import structlog

from django.core.exceptions import PermissionDenied

logger = structlog.get_logger(__name__)


# ── Quota table ────────────────────────────────────────────────────────────────
# Sized against the combined free-tier budget of the upstream providers
# (Groq ~14.4k req/day + Gemini ~1k req/day) with headroom for growth.
# An agent_run costs ~10-20 upstream calls; an ai_query costs ~1-3.
# -1 means unlimited.

QUOTAS = {
    "ai_queries": {"daily": 40, "monthly": 300},
    "agent_runs": {"daily": 5, "monthly": 30},
    "documents": {"daily": 10, "monthly": 50},
    "automations": {"daily": -1, "monthly": 20},
    "bookmarks": {"daily": -1, "monthly": -1},
}

# Every feature is available to every user. Kept as a table (rather than
# deleting the concept) so a feature can be disabled globally during an
# incident without touching call sites.
FEATURES = {
    "semantic_search": True,
    "api_access": True,
    "google_drive": True,
    "private_repos": True,
    "teams": True,
    "custom_ai": True,
    "audit_logs": True,
    "sso": True,
    "advanced_analytics": True,
}


# ── Referral bonus ─────────────────────────────────────────────────────────────
# Referrals grant extra quota instead of paid-plan time. The bonus is derived
# from ReferralCode.uses, so no extra model or migration is needed.

BONUS_PER_REFERRAL = {"ai_queries": 100, "agent_runs": 10, "documents": 15}
MAX_BONUS_REFERRALS = 5


def get_referral_bonus(user, resource: str) -> int:
    """Extra monthly allowance earned from referrals. 0 if none."""
    per_referral = BONUS_PER_REFERRAL.get(resource, 0)
    if not per_referral:
        return 0
    try:
        uses = user.referral_code.uses
    except Exception:
        return 0
    return min(uses, MAX_BONUS_REFERRALS) * per_referral


# ── Public helpers ─────────────────────────────────────────────────────────────


def get_quota(user, resource: str, period: str = "monthly") -> int:
    """
    Return the user's limit for a resource in a period ('daily'/'monthly').

    -1 means unlimited. Referral bonuses apply to the monthly ceiling only —
    the daily cap stays fixed so a well-referred user still can't drain the
    day's upstream budget in one sitting.
    """
    limit = QUOTAS.get(resource, {}).get(period, 0)
    if limit == -1:
        return -1
    if period == "monthly":
        limit += get_referral_bonus(user, resource)
    return limit


def user_has_feature(user, feature: str) -> bool:
    """Return True if the feature is enabled. All features are free."""
    return FEATURES.get(feature, False)


def check_quota(user, resource: str, current_usage: int | None = None) -> None:
    """
    Check the user against both the daily and monthly ceiling for a resource.

    Raises PermissionDenied (error_code='quota_exceeded') if either is hit.
    The daily cap is checked first so the error message names the ceiling the
    user will recover from soonest.

    If current_usage is None, usage is counted from the DB. Pass it explicitly
    to avoid the extra query on hot paths.
    """
    for period in ("daily", "monthly"):
        limit = get_quota(user, resource, period)
        if limit == -1:
            continue

        usage = (
            current_usage
            if current_usage is not None
            else _count_usage(user, resource, period)
        )

        if usage >= limit:
            logger.warning(
                "quota_exceeded",
                user=getattr(user, "email", str(user)),
                resource=resource,
                period=period,
                usage=usage,
                limit=limit,
            )
            resets = "tomorrow" if period == "daily" else "on the 1st of next month"
            exc = PermissionDenied(
                f"You've reached your {period} limit for {resource} "
                f"({usage}/{limit}). This resets {resets}. "
                f"Invite others with your referral code to raise your monthly cap."
            )
            exc.error_code = "quota_exceeded"  # type: ignore[attr-defined]
            exc.resource = resource  # type: ignore[attr-defined]
            exc.period = period  # type: ignore[attr-defined]
            exc.limit = limit  # type: ignore[attr-defined]
            exc.usage = usage  # type: ignore[attr-defined]
            raise exc


def get_usage_summary(user) -> dict:
    """
    Return usage/limit for every resource across both periods.

    Powers the account page's quota display.
    """
    return {
        resource: {
            period: {
                "usage": _count_usage(user, resource, period),
                "limit": get_quota(user, resource, period),
            }
            for period in ("daily", "monthly")
            if QUOTAS[resource][period] != -1
        }
        for resource in QUOTAS
    }


# ── Usage counting ─────────────────────────────────────────────────────────────


def _period_start(period: str):
    """Start of the current day or calendar month."""
    from django.utils import timezone

    now = timezone.now()
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight if period == "daily" else midnight.replace(day=1)


def _count_usage(user, resource: str, period: str = "monthly") -> int:
    """Count a user's usage of a resource since the start of the period."""
    start = _period_start(period)

    # (model path, whether the model is time-scoped) per resource
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

    if resource == "documents":
        try:
            from apps.documents.models import GeneratedDocument

            return GeneratedDocument.objects.filter(
                user=user, created_at__gte=start
            ).count()
        except Exception:
            return 0

    # Automations and bookmarks are standing objects, not events — count all of
    # them regardless of period rather than only those created since `start`.
    if resource == "automations":
        try:
            from apps.automation.models import Workflow

            return Workflow.objects.filter(user=user).count()
        except Exception:
            return 0

    if resource == "bookmarks":
        try:
            from apps.core.models import Bookmark

            return Bookmark.objects.filter(user=user).count()
        except Exception:
            return 0

    return 0
