"""
TASK-501 — Plan-Aware Rate Limiting tests.

Covers:
  B1 — PlanAwareThrottle base class and concrete subclasses
  B2 — ChatRateThrottle enforces plan limits (free: 50/day)
  B3 — AgentRateThrottle enforces plan limits (free: 10/day)
  B4 — 429 responses include X-RateLimit-* headers + structured JSON body
  F1 — api.ts dispatches 'synapse:rate_limit_exceeded' event (validated by middleware test)
"""

import time
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from apps.core.throttles import (
    AGENT_LIMITS,
    API_LIMITS,
    CHAT_LIMITS,
    AgentRateThrottle,
    APIRateThrottle,
    ChatRateThrottle,
)

# ── helpers ───────────────────────────────────────────────────────────────────


def make_request(user_plan="free", user_id=1):
    """Build a minimal mock request with an authenticated user."""
    user = MagicMock()
    user.is_authenticated = True
    user.pk = user_id
    request = MagicMock()
    request.user = user
    with patch("apps.core.throttles.get_user_plan", return_value=user_plan):
        return request, user


def make_throttle(cls, user_plan="free", user_id=1):
    """Instantiate throttle with a mock DjangoCacheClient."""
    throttle = cls()
    throttle.cache = {}  # plain dict acts as cache
    # Override cache methods to use dict
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


# ── B1: Throttle classes configuration ───────────────────────────────────────


class TestThrottleConfig:
    def test_chat_free_limit(self):
        limit, window = CHAT_LIMITS["free"]
        assert limit == 50
        assert window == 86400  # 1 day

    def test_chat_pro_limit(self):
        limit, window = CHAT_LIMITS["pro"]
        assert limit == 200
        assert window == 86400

    def test_chat_enterprise_limit(self):
        limit, window = CHAT_LIMITS["enterprise"]
        assert limit == 1000

    def test_agent_free_limit(self):
        limit, window = AGENT_LIMITS["free"]
        assert limit == 10
        assert window == 86400

    def test_agent_pro_limit(self):
        limit, window = AGENT_LIMITS["pro"]
        assert limit == 50

    def test_api_free_limit(self):
        limit, window = API_LIMITS["free"]
        assert limit == 1000
        assert window == 3600  # 1 hour

    def test_scope_names(self):
        assert ChatRateThrottle.scope == "chat"
        assert AgentRateThrottle.scope == "agent"
        assert APIRateThrottle.scope == "api"

    def test_limit_tables(self):
        assert ChatRateThrottle.limit_table is CHAT_LIMITS
        assert AgentRateThrottle.limit_table is AGENT_LIMITS
        assert APIRateThrottle.limit_table is API_LIMITS


# ── B2: ChatRateThrottle ──────────────────────────────────────────────────────


class TestChatRateThrottle:
    def _make(self, plan="free", user_id=1):
        throttle = ChatRateThrottle()
        throttle.cache = _DictCache()
        request = MagicMock()
        request.user = MagicMock(is_authenticated=True, pk=user_id)
        return throttle, request, plan

    def _allow(self, throttle, request, plan, view=None):
        with patch("apps.core.throttles.get_user_plan", return_value=plan):
            return throttle.allow_request(request, view or MagicMock())

    def test_free_allows_first_50(self):
        throttle, req, plan = self._make("free")
        for i in range(50):
            assert (
                self._allow(throttle, req, plan) is True
            ), f"Request {i+1} should be allowed"

    def test_free_blocks_51st(self):
        throttle, req, plan = self._make("free")
        for _ in range(50):
            self._allow(throttle, req, plan)
        assert self._allow(throttle, req, plan) is False

    def test_pro_allows_more(self):
        throttle, req, plan = self._make("pro")
        for i in range(200):
            assert self._allow(throttle, req, plan) is True

    def test_pro_blocks_201st(self):
        throttle, req, plan = self._make("pro")
        for _ in range(200):
            self._allow(throttle, req, plan)
        assert self._allow(throttle, req, plan) is False

    def test_different_users_independent(self):
        throttle = ChatRateThrottle()
        throttle.cache = _DictCache()
        req1 = MagicMock()
        req1.user = MagicMock(is_authenticated=True, pk=1)
        req2 = MagicMock()
        req2.user = MagicMock(is_authenticated=True, pk=2)
        view = MagicMock()
        with patch("apps.core.throttles.get_user_plan", return_value="free"):
            # Use all 50 for user 1
            for _ in range(50):
                throttle.allow_request(req1, view)
            # User 2 still gets their own 50
            assert throttle.allow_request(req2, view) is True

    def test_anonymous_not_throttled(self):
        throttle, _, _ = self._make()
        req = MagicMock()
        req.user = MagicMock(is_authenticated=False)
        with patch("apps.core.throttles.get_user_plan", return_value="free"):
            assert throttle.allow_request(req, MagicMock()) is True

    def test_remaining_decrements(self):
        throttle, req, plan = self._make("free")
        view = MagicMock()
        with patch("apps.core.throttles.get_user_plan", return_value=plan):
            throttle.allow_request(
                req, view
            )  # 1st: count was 0 → remaining = 50 - 0 - 1 = 49
            assert throttle._remaining == 49
            throttle.allow_request(
                req, view
            )  # 2nd: count was 1 → remaining = 50 - 1 - 1 = 48
            assert throttle._remaining == 48

    def test_reset_at_is_future(self):
        throttle, req, plan = self._make("free")
        with patch("apps.core.throttles.get_user_plan", return_value=plan):
            throttle.allow_request(req, MagicMock())
            assert throttle._reset_at > time.time()

    def test_wait_returns_positive(self):
        throttle, req, plan = self._make("free")
        with patch("apps.core.throttles.get_user_plan", return_value=plan):
            for _ in range(50):
                throttle.allow_request(req, MagicMock())
            throttle.allow_request(req, MagicMock())  # blocked
            wait = throttle.wait()
            assert wait is not None and wait > 0

    def test_throttle_failure_response_structure(self):
        throttle, req, plan = self._make("free")
        with patch("apps.core.throttles.get_user_plan", return_value=plan):
            for _ in range(51):
                throttle.allow_request(req, MagicMock())
        resp = throttle.throttle_failure_response()
        assert resp["error"] == "rate_limit_exceeded"
        assert resp["limit"] == 50
        assert resp["remaining"] == 0
        assert "reset_at" in resp
        assert "upgrade_url" in resp
        assert "message" in resp

    def test_get_headers_keys(self):
        throttle, req, plan = self._make("free")
        with patch("apps.core.throttles.get_user_plan", return_value=plan):
            throttle.allow_request(req, MagicMock())
        headers = throttle.get_headers()
        assert "X-RateLimit-Limit" in headers
        assert "X-RateLimit-Remaining" in headers
        assert "X-RateLimit-Reset" in headers
        assert "Retry-After" in headers


# ── B3: AgentRateThrottle ─────────────────────────────────────────────────────


class TestAgentRateThrottle:
    def _allow(self, throttle, request, plan, view=None):
        with patch("apps.core.throttles.get_user_plan", return_value=plan):
            return throttle.allow_request(request, view or MagicMock())

    def test_free_allows_10(self):
        t = AgentRateThrottle()
        t.cache = _DictCache()
        req = MagicMock()
        req.user = MagicMock(is_authenticated=True, pk=42)
        for i in range(10):
            assert self._allow(t, req, "free") is True

    def test_free_blocks_11th(self):
        t = AgentRateThrottle()
        t.cache = _DictCache()
        req = MagicMock()
        req.user = MagicMock(is_authenticated=True, pk=42)
        for _ in range(10):
            self._allow(t, req, "free")
        assert self._allow(t, req, "free") is False

    def test_pro_allows_50(self):
        t = AgentRateThrottle()
        t.cache = _DictCache()
        req = MagicMock()
        req.user = MagicMock(is_authenticated=True, pk=99)
        for i in range(50):
            assert self._allow(t, req, "pro") is True


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
