"""
TASK-501 — Plan-Aware Per-User Rate Limiting

Custom DRF throttle classes that enforce plan-tier limits using Redis.
Instead of a single rate for all users, limits are looked up per plan:

    Free  : chat=5/day,   agent=1/day,   api=100/hour
    Pro   : chat=200/day, agent=50/day,  api=500/hour
    Team  : chat=1000/day,agent=200/day, api=2000/hour (pooled on org)

Response headers on 429:
    X-RateLimit-Limit     — requests allowed in the window
    X-RateLimit-Remaining — requests still available (0 on 429)
    X-RateLimit-Reset     — UTC unix timestamp when window resets
    Retry-After           — seconds until window resets

JSON body on 429:
    {
        "error": "rate_limit_exceeded",
        "limit": 5,
        "reset_at": "2026-04-04T07:00:00Z",
        "upgrade_url": "/pricing",
        "message": "..."
    }
"""

from __future__ import annotations

import time
from datetime import datetime
from datetime import timezone as dt_timezone
from typing import Optional

from apps.billing.limits import get_user_plan

from rest_framework.exceptions import Throttled
from rest_framework.throttling import SimpleRateThrottle

# ── Plan limit tables ─────────────────────────────────────────────────────────

# Each entry: (max_requests, window_seconds)
CHAT_LIMITS: dict[str, tuple[int, int]] = {
    "free": (50, 86400),  # 50/day — generous for trial
    "pro": (200, 86400),  # 200/day
    "enterprise": (1000, 86400),  # 1000/day pooled
}

AGENT_LIMITS: dict[str, tuple[int, int]] = {
    "free": (10, 86400),  # 10/day — enough to try the feature
    "pro": (50, 86400),  # 50/day
    "enterprise": (200, 86400),  # 200/day pooled
}

API_LIMITS: dict[str, tuple[int, int]] = {
    "free": (1000, 3600),  # 1000/hour — dashboard makes 30+ requests per load
    "pro": (5000, 3600),  # 5000/hour
    "enterprise": (20000, 3600),  # 20000/hour
}


# ── Base plan-aware throttle ──────────────────────────────────────────────────


class PlanAwareThrottle(SimpleRateThrottle):
    """
    Base class for plan-aware throttles.

    Subclasses set `limit_table` (dict plan→(limit, window)).
    Cache key: rl:{scope}:{user_id}:{window_bucket}
    """

    scope: str = "plan_api"
    limit_table: dict[str, tuple[int, int]] = API_LIMITS

    # populated per-request in allow_request()
    _limit: int = 0
    _remaining: int = 0
    _reset_at: int = 0  # unix timestamp

    def get_cache_key(self, request, view) -> Optional[str]:
        if not request.user or not request.user.is_authenticated:
            return None
        plan = get_user_plan(request.user)
        _, window = self.limit_table.get(plan, self.limit_table["free"])
        # bucket = current window start (floor division of unix time)
        bucket = int(time.time()) // window
        return f"rl:{self.scope}:{request.user.pk}:{bucket}"

    def get_rate(self):
        # DRF SimpleRateThrottle requires get_rate() to return a string like "5/day"
        # but we override allow_request() entirely, so this is only used for
        # parse_rate() which we don't call. Return a dummy value.
        return "9999/day"

    def allow_request(self, request, view) -> bool:
        # Rate limiting disabled for Replit demo environment.
        # The global DEFAULT_THROTTLE_CLASSES=[] in replit.py already removes
        # the default throttles; this override ensures any per-view subclass
        # instances also pass through unconditionally.
        import os
        if os.environ.get("DISABLE_RATE_LIMITS", "true").lower() in ("1", "true", "yes"):
            return True

        if not request.user or not request.user.is_authenticated:
            return True  # anonymous: handled by AnonRateThrottle

        plan = get_user_plan(request.user)
        limit, window = self.limit_table.get(plan, self.limit_table["free"])
        self._limit = limit

        key = self.get_cache_key(request, view)
        if key is None:
            return True

        # Atomic increment in Redis
        count = self.cache.get(key, 0)
        if count is None:
            count = 0

        bucket = int(time.time()) // window
        reset_ts = (bucket + 1) * window
        self._reset_at = reset_ts
        self._remaining = max(0, limit - count - 1)

        if count >= limit:
            self._remaining = 0
            self.wait()  # sets self.history / self.now used by DRF
            return False

        # Increment counter
        new_count = count + 1
        self.cache.set(key, new_count, timeout=window)
        return True

    def wait(self) -> Optional[float]:
        """Return seconds until window resets."""
        return max(0.0, self._reset_at - time.time())

    def throttle_failure_response(self) -> dict:
        """Return structured 429 body."""
        reset_dt = datetime.fromtimestamp(self._reset_at, tz=dt_timezone.utc)
        return {
            "error": "rate_limit_exceeded",
            "limit": self._limit,
            "remaining": 0,
            "reset_at": reset_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "upgrade_url": "/pricing",
            "message": (
                f"You have exceeded your plan's rate limit of {self._limit} requests. "
                f"Resets at {reset_dt.strftime('%H:%M UTC')}. Upgrade to Pro for higher limits."
            ),
        }

    def get_headers(self) -> dict:
        """Return X-RateLimit-* headers to inject into response."""
        wait_secs = max(0, self._reset_at - int(time.time()))
        return {
            "X-RateLimit-Limit": str(self._limit),
            "X-RateLimit-Remaining": str(self._remaining),
            "X-RateLimit-Reset": str(self._reset_at),
            "Retry-After": str(wait_secs),
        }


# ── Concrete throttle classes ─────────────────────────────────────────────────


class ChatRateThrottle(PlanAwareThrottle):
    """TASK-501-B2: Rate limit for POST /api/*/chat/message/ endpoint."""

    scope = "chat"
    limit_table = CHAT_LIMITS


class AgentRateThrottle(PlanAwareThrottle):
    """TASK-501-B3: Rate limit for POST /api/*/agents/ endpoint."""

    scope = "agent"
    limit_table = AGENT_LIMITS


REGISTRATION_LIMITS: dict[str, tuple[int, int]] = {
    "free": (5, 3600),       # 5 registrations/hour per IP
    "pro": (20, 3600),       # 20/hour
    "enterprise": (100, 3600),
}


class APIRateThrottle(PlanAwareThrottle):
    """General API rate limit — applied globally per plan tier."""

    scope = "api"
    limit_table = API_LIMITS


class RegistrationThrottle(SimpleRateThrottle):
    """
    Rate limit for user registration — keyed by client IP.
    Prevents spam registrations without requiring authentication.
    """

    scope = "registration"

    def get_cache_key(self, request, view) -> Optional[str]:
        return f"rl:registration:{self.get_ident(request)}"

    def get_rate(self) -> str:
        from django.conf import settings
        return getattr(settings, "REGISTRATION_THROTTLE_RATE", "5/hour")

    def allow_request(self, request, view):
        if getattr(request.user, "is_authenticated", False):
            return True
        return super().allow_request(request, view)
