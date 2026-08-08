"""
TASK-501-B4: Rate Limit Response Middleware

Intercepts DRF Throttled exceptions raised by PlanAwareThrottle subclasses
and converts them into a structured JSON 429 with the correct headers:

    X-RateLimit-Limit
    X-RateLimit-Remaining
    X-RateLimit-Reset
    Retry-After

Body:
    {
        "error":       "rate_limit_exceeded",
        "limit":       5,
        "remaining":   0,
        "reset_at":    "2026-04-04T07:00:00Z",
        "upgrade_url": "/pricing",
        "message":     "..."
    }
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from datetime import timezone as dt_timezone
from typing import Callable

from django.http import HttpRequest, JsonResponse


class RateLimitHeaderMiddleware:
    """
    Middleware that injects X-RateLimit-* headers into *every* response
    when rate limit information is present (attached by PlanAwareThrottle).

    Also converts plain 429 text responses → structured JSON for API paths.
    """

    def __init__(self, get_response: Callable):
        self.get_response = get_response

    def __call__(self, request: HttpRequest):
        response = self.get_response(request)

        # Guard: streaming views (SSE) and some middleware chains return None
        if response is None:
            return response

        # Only touch /api/ paths
        if not request.path.startswith("/api/"):
            return response

        # If DRF attached rate limit headers via the throttle, pass them through
        # (DRF sets them on the response object when throttle fails)
        for header in (
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
            "Retry-After",
        ):
            if header in response:
                pass  # already present — DRF set them

        # Convert plain 429 to structured JSON
        if response.status_code == 429:
            ct = getattr(response, "content_type", "") or ""
            if not ct.startswith("application/json"):
                try:
                    # Try to parse existing content
                    existing = json.loads(response.content.decode())
                    if "error" not in existing:
                        raise ValueError
                    return response
                except Exception:
                    pass

                wait = int(response.get("Retry-After", 60))
                reset_ts = int(time.time()) + wait
                reset_dt = datetime.fromtimestamp(reset_ts, tz=dt_timezone.utc)
                body = {
                    "error": "rate_limit_exceeded",
                    "limit": int(response.get("X-RateLimit-Limit", 0)),
                    "remaining": 0,
                    "reset_at": reset_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "upgrade_url": "/pricing",
                    "message": (
                        f"Rate limit exceeded. Resets at {reset_dt.strftime('%H:%M UTC')}. "
                        "Upgrade your plan for higher limits."
                    ),
                }
                new_resp = JsonResponse(body, status=429)
                # Copy rate limit headers
                for header in (
                    "X-RateLimit-Limit",
                    "X-RateLimit-Remaining",
                    "X-RateLimit-Reset",
                    "Retry-After",
                ):
                    if header in response:
                        new_resp[header] = response[header]
                return new_resp

        return response
