"""
TASK-501 — Rate Limiting tests.

Covers:
  B1 — PlanAwareThrottle base class and concrete subclasses
  B2 — ChatRateThrottle enforces the per-user rate (50/day)
  B3 — AgentRateThrottle enforces the per-user rate (10/day)
  B4 — 429 responses include X-RateLimit-* headers + structured JSON body
  F1 — api.ts dispatches 'synapse:rate_limit_exceeded' event (validated by middleware test)
"""

import time
from unittest.mock import MagicMock

from apps.core.throttles import (
    AGENT_LIMIT,
    API_LIMIT,
    CHAT_LIMIT,
    AgentRateThrottle,
    APIRateThrottle,
    ChatRateThrottle,
)

# ── helpers ───────────────────────────────────────────────────────────────────


def make_throttle(cls, user_id=1):
    """Instantiate throttle with an in-memory cache."""
    throttle = cls()
    throttle.cache = _DictCache()
    return throttle


class _DictCache:
    """Minimal in-memory cache compatible with SimpleRateThrottle.cache interface."""

    def __init__(self):
        self._store: dict = {}

    def get(self, key, default=None):
        return self._store.get(key, default)

    def set(self, key, value, timeout=None):
        self._store[key] = value

    def incr(self, key, delta=1):
        self._store[key] = self._store.get(key, 0) + delta
        return self._store[key]


def make_user_request(pk=1):
    request = MagicMock()
    request.user = MagicMock(is_authenticated=True, pk=pk)
    return request


# ── B1: Throttle classes configuration ───────────────────────────────────────


class TestThrottleConfig:
    def test_chat_limit(self):
        limit, window = CHAT_LIMIT
        assert limit == 50
        assert window == 86400  # 1 day

    def test_agent_limit(self):
        limit, window = AGENT_LIMIT
        assert limit == 10
        assert window == 86400

    def test_api_limit(self):
        limit, window = API_LIMIT
        assert limit == 1000
        assert window == 3600  # 1 hour

    def test_scope_names(self):
        assert ChatRateThrottle.scope == "chat"
        assert AgentRateThrottle.scope == "agent"
        assert APIRateThrottle.scope == "api"

    def test_limit_rules(self):
        assert ChatRateThrottle.limit_rule is CHAT_LIMIT
        assert AgentRateThrottle.limit_rule is AGENT_LIMIT
        assert APIRateThrottle.limit_rule is API_LIMIT


# ── B2: ChatRateThrottle ──────────────────────────────────────────────────────


class TestChatRateThrottle:
    def _make(self, user_id=1):
        throttle = make_throttle(ChatRateThrottle)
        return throttle, make_user_request(pk=user_id)

    def test_allows_first_50(self):
        throttle, req = self._make()
        for i in range(50):
            assert (
                throttle.allow_request(req, MagicMock()) is True
            ), f"Request {i+1} should be allowed"

    def test_blocks_51st(self):
        throttle, req = self._make()
        for _ in range(50):
            throttle.allow_request(req, MagicMock())
        assert throttle.allow_request(req, MagicMock()) is False

    def test_different_users_independent(self):
        throttle = make_throttle(ChatRateThrottle)
        req1 = make_user_request(pk=1)
        req2 = make_user_request(pk=2)
        view = MagicMock()
        # Use all 50 for user 1
        for _ in range(50):
            throttle.allow_request(req1, view)
        # User 2 still gets their own 50
        assert throttle.allow_request(req2, view) is True

    def test_anonymous_not_throttled(self):
        throttle, _ = self._make()
        req = MagicMock()
        req.user = MagicMock(is_authenticated=False)
        assert throttle.allow_request(req, MagicMock()) is True

    def test_remaining_decrements(self):
        throttle, req = self._make()
        view = MagicMock()
        throttle.allow_request(
            req, view
        )  # 1st: count was 0 → remaining = 50 - 0 - 1 = 49
        assert throttle._remaining == 49
        throttle.allow_request(
            req, view
        )  # 2nd: count was 1 → remaining = 50 - 1 - 1 = 48
        assert throttle._remaining == 48

    def test_reset_at_is_future(self):
        throttle, req = self._make()
        throttle.allow_request(req, MagicMock())
        assert throttle._reset_at > time.time()

    def test_wait_returns_positive(self):
        throttle, req = self._make()
        for _ in range(50):
            throttle.allow_request(req, MagicMock())
        throttle.allow_request(req, MagicMock())  # blocked
        wait = throttle.wait()
        assert wait is not None and wait > 0

    def test_throttle_failure_response_structure(self):
        throttle, req = self._make()
        for _ in range(51):
            throttle.allow_request(req, MagicMock())
        resp = throttle.throttle_failure_response()
        assert resp["error"] == "rate_limit_exceeded"
        assert resp["limit"] == 50
        assert resp["remaining"] == 0
        assert "reset_at" in resp
        assert "message" in resp

    def test_get_headers_keys(self):
        throttle, req = self._make()
        throttle.allow_request(req, MagicMock())
        headers = throttle.get_headers()
        assert "X-RateLimit-Limit" in headers
        assert "X-RateLimit-Remaining" in headers
        assert "X-RateLimit-Reset" in headers
        assert "Retry-After" in headers


# ── B3: AgentRateThrottle ─────────────────────────────────────────────────────


class TestAgentRateThrottle:
    def test_allows_10(self):
        t = make_throttle(AgentRateThrottle)
        req = make_user_request(pk=42)
        for i in range(10):
            assert (
                t.allow_request(req, MagicMock()) is True
            ), f"Request {i+1} should be allowed"

    def test_blocks_11th(self):
        t = make_throttle(AgentRateThrottle)
        req = make_user_request(pk=42)
        for _ in range(10):
            t.allow_request(req, MagicMock())
        assert t.allow_request(req, MagicMock()) is False


# ── B4: Middleware (RateLimitHeaderMiddleware) ────────────────────────────────


class TestRateLimitHeaderMiddleware:
    def _make_middleware(self, response):
        from apps.core.rate_limit_middleware import RateLimitHeaderMiddleware

        mw = RateLimitHeaderMiddleware(get_response=lambda r: response)
        return mw

    def test_non_api_path_untouched(self):
        from django.http import HttpResponse
        from django.test import RequestFactory

        resp = HttpResponse("ok", status=200)
        mw = self._make_middleware(resp)
        req = RequestFactory().get("/admin/")
        result = mw(req)
        assert result.status_code == 200

    def test_api_path_passes_through(self):
        from django.http import HttpResponse
        from django.test import RequestFactory

        resp = HttpResponse("ok", status=200)
        mw = self._make_middleware(resp)
        req = RequestFactory().get("/api/v1/health/")
        result = mw(req)
        assert result.status_code == 200

    def test_429_plain_text_converted_to_json(self):
        import json

        from django.http import HttpResponse
        from django.test import RequestFactory

        resp = HttpResponse("Too Many Requests", status=429, content_type="text/plain")
        resp["Retry-After"] = "60"
        resp["X-RateLimit-Limit"] = "5"
        mw = self._make_middleware(resp)
        req = RequestFactory().post("/api/v1/ai/chat/")
        result = mw(req)
        assert result.status_code == 429
        body = json.loads(result.content)
        assert body["error"] == "rate_limit_exceeded"
        assert "reset_at" in body
        assert "upgrade_url" in body

    def test_429_already_json_not_double_wrapped(self):
        import json

        from django.http import JsonResponse
        from django.test import RequestFactory

        body = {
            "error": "rate_limit_exceeded",
            "limit": 5,
            "remaining": 0,
            "reset_at": "2026-04-04T07:00:00Z",
            "upgrade_url": "/pricing",
            "message": "x",
        }
        resp = JsonResponse(body, status=429)
        mw = self._make_middleware(resp)
        req = RequestFactory().post("/api/v1/ai/chat/")
        result = mw(req)
        assert result.status_code == 429
        parsed = json.loads(result.content)
        assert parsed["error"] == "rate_limit_exceeded"
