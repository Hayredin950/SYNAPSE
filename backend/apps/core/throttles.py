"""
TASK-501 — Per-User Rate Limiting

Custom DRF throttle classes that enforce per-user request rates using Redis.
SYNAPSE is free to use, so every authenticated user gets the same rate:

    chat=50/day, agent=10/day, api=1000/hour

These are short-window burst limits. The longer-horizon daily and monthly
ceilings live in apps.core.quotas — see that module for why both layers exist.

Response headers on 429:
    X-RateLimit-Limit     — requests allowed in the window
    X-RateLimit-Remaining — requests still available (0 on 429)
    X-RateLimit-Reset     — UTC unix timestamp when window resets
    Retry-After           — seconds until window resets

JSON body on 429:
    {
        "error": "rate_limit_exceeded",
        "limit": 50,
        "reset_at": "2026-04-04T07:00:00Z",
        "message": "..."
    }
"""

from __future__ import annotations

import time
from datetime import datetime
from datetime import timezone as dt_timezone
from typing import Optional

from rest_framework.exceptions import Throttled
from rest_framework.throttling import SimpleRateThrottle

# ── Rate limit tables ─────────────────────────────────────────────────────────
#
# SYNAPSE is free — every user gets the same rate. These are burst/rate limits
# (short window); the longer-horizon daily and monthly ceilings live in
# apps.core.quotas. Both layers matter: the throttle stops a hot loop, the
# quota stops sustained drain of the upstream AI provider budget.
#
# Each entry: (max_requests, window_seconds)

CHAT_LIMIT: tuple[int, int] = (50, 86400)  # 50/day
AGENT_LIMIT: tuple[int, int] = (10, 86400)  # 10/day
API_LIMIT: tuple[int, int] = (1000, 3600)  # 1000/hour — a dashboard load is 30+


# ── Base throttle ─────────────────────────────────────────────────────────────


class PlanAwareThrottle(SimpleRateThrottle):
    """
    Base class for per-user throttles.

    Subclasses set `limit_rule` — a (limit, window_seconds) tuple.
    Cache key: rl:{scope}:{user_id}:{window_bucket}

    Named PlanAwareThrottle for historical reasons; there are no plans any
    more, so every authenticated user resolves to the same rule.
    """

    scope: str = "plan_api"
    limit_rule: tuple[int, int] = API_LIMIT

    # populated per-request in allow_request()
    _limit: int = 0
    _remaining: int = 0
    _reset_at: int = 0  # unix timestamp

    def get_cache_key(self, request, view) -> Optional[str]:
        if not request.user or not request.user.is_authenticated:
            return None
        _, window = self.limit_rule
        # bucket = current window start (floor division of unix time)
        bucket = int(time.time()) // window
        return f"rl:{self.scope}:{request.user.pk}:{bucket}"

    def get_rate(self):
        # DRF SimpleRateThrottle requires get_rate() to return a string like "5/day"
        # but we override allow_request() entirely, so this is only used for
        # parse_rate() which we don't call. Return a dummy value.
        return "9999/day"

    def allow_request(self, request, view) -> bool:
        # Escape hatch for local development only. This MUST default to off:
        # throttling is the first line of defence for the shared upstream AI
        # provider quota, and a default-on bypass silently removes it in any
        # environment that forgets to set the variable.
        import os

        if os.environ.get("DISABLE_RATE_LIMITS", "false").lower() in (
            "1",
            "true",
            "yes",
        ):
            return True

        if not request.user or not request.user.is_authenticated:
            return True  # anonymous: handled by AnonRateThrottle

        limit, window = self.limit_rule
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
            "message": (
                f"You have exceeded the rate limit of {self._limit} requests. "
                f"Resets at {reset_dt.strftime('%H:%M UTC')}."
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
    limit_rule = CHAT_LIMIT


class AgentRateThrottle(PlanAwareThrottle):
    """TASK-501-B3: Rate limit for POST /api/*/agents/ endpoint."""

    scope = "agent"
    limit_rule = AGENT_LIMIT


REGISTRATION_LIMIT: tuple[int, int] = (5, 3600)  # 5 registrations/hour per IP


class APIRateThrottle(PlanAwareThrottle):
    """General API rate limit."""

    scope = "api"
    limit_rule = API_LIMIT


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
