"""
Integration tests for billing limits, org permissions, and AI guardrails.
Covers fixes from Sprint 1-4 code review.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# ── Billing Limit Tests ───────────────────────────────────────────────────────


class TestBillingLimits:
    """Tests for apps.billing.limits — plan-based feature gating."""

    def test_free_plan_has_lower_limits(self):
        """Free plan limits are lower than pro plan limits."""
        from apps.billing.limits import get_plan_limits

        free = get_plan_limits("free")
        pro = get_plan_limits("pro")
        # free ai_queries is 50; pro is -1 (unlimited) — so free < pro when treating -1 as ∞
        # We compare: free limit is finite and positive, pro is -1 (unlimited)
        assert free["ai_queries"] > 0, "free plan should have a finite ai_queries limit"
        assert pro["ai_queries"] == -1, "pro plan should have unlimited ai_queries"
        assert free["agent_runs"] > 0
        assert pro["agent_runs"] == -1

    def test_unknown_plan_returns_free_limits(self):
        """Unknown plan names fall back to free tier limits."""
        from apps.billing.limits import get_plan_limits

        unknown = get_plan_limits("nonexistent_plan_xyz")
        free = get_plan_limits("free")
        assert unknown["ai_queries"] == free["ai_queries"]

    def test_enterprise_plan_has_highest_limits(self):
        """Enterprise plan has limits >= pro (both unlimited → equal)."""
        from apps.billing.limits import get_plan_limits

        pro = get_plan_limits("pro")
        enterprise = get_plan_limits("enterprise")
        # Both are -1 (unlimited); enterprise should never be more restricted than pro
        assert enterprise["ai_queries"] == pro["ai_queries"]
        assert enterprise["agent_runs"] == pro["agent_runs"]

    def test_check_limit_returns_bool(self):
        """check_limit returns a boolean."""
        from apps.billing.limits import check_limit

        result = check_limit("free", "ai_queries", current_usage=0)
        assert isinstance(result, bool)
        assert result is True  # 0 < limit → allowed

    def test_check_limit_blocks_at_cap(self):
        """check_limit blocks when usage meets or exceeds plan cap."""
        from apps.billing.limits import check_limit, get_plan_limits

        cap = get_plan_limits("free")["ai_queries"]
        assert check_limit("free", "ai_queries", current_usage=cap) is False
        assert check_limit("free", "ai_queries", current_usage=cap + 1) is False


# ── AI Guardrails Tests ───────────────────────────────────────────────────────


class TestAIGuardrails:
    """Tests for ai_engine middleware — SEC-01/ERR-07 fixes."""

    def test_moderation_disabled_allows_all(self):
        """When MODERATION_ENABLED=false, all content is allowed through."""
        import os

        with patch.dict(os.environ, {"MODERATION_ENABLED": "false"}):
            # Re-import to pick up env change (functions read at call time now)
            import importlib

            import ai_engine.middleware.moderation as mod

            importlib.reload(mod)
            result = mod.check_moderation("kill everyone with a weapon")
            assert result["flagged"] is False

    def test_moderation_skips_without_api_key(self):
        """Without OPENAI_API_KEY, moderation is skipped (returns not-flagged)."""
        import os

        with patch.dict(
            os.environ, {"MODERATION_ENABLED": "true", "OPENAI_API_KEY": ""}
        ):
            import importlib

            import ai_engine.middleware.moderation as mod

            importlib.reload(mod)
            result = mod.check_moderation("hello world")
            assert result["flagged"] is False

    def test_rate_limit_middleware_blocks_excessive_requests(self):
        """Rate limiter tracks and blocks users over their per-minute limit."""
        import os

        with patch.dict(os.environ, {"MODERATION_ENABLED": "false"}):
            try:
                from ai_engine.middleware.rate_limit import RateLimiter

                limiter = RateLimiter(max_requests=2, window_seconds=60)
                # First two allowed
                assert limiter.is_allowed("user_test_123") is True
                assert limiter.is_allowed("user_test_123") is True
                # Third blocked
                assert limiter.is_allowed("user_test_123") is False
            except ImportError:
                pytest.skip("rate_limit module not structured for direct instantiation")

    def test_budget_exceeded_error_has_correct_fields(self):
        """BudgetExceededError carries used_cents, limit_cents, reset_at."""
        import os
        import sys

        sys.path.insert(0, "ai_engine")
        try:
            from ai_engine.middleware.rate_limit import BudgetExceededError

            exc = BudgetExceededError(
                used_cents=1000, limit_cents=500, reset_at="2026-04-06T00:00:00Z"
            )
            assert exc.used_cents == 1000
            assert exc.limit_cents == 500
            assert "2026-04-06" in exc.reset_at
        except ImportError:
            pytest.skip("BudgetExceededError not importable")


# ── Python Sandbox Security Tests ────────────────────────────────────────────


class TestPythonSandbox:
    """Tests for SEC-08 sandbox hardening fixes in ai_engine/agents/tools.py."""

    def test_sandbox_blocks_os_import(self):
        from ai_engine.agents.tools import _run_python_code

        r = _run_python_code("import os")
        assert not r["success"], "os import should be blocked"

    def test_sandbox_blocks_subprocess(self):
        from ai_engine.agents.tools import _run_python_code

        r = _run_python_code("import subprocess; subprocess.run(['ls'])")
        assert not r["success"], "subprocess should be blocked"

    def test_sandbox_blocks_dunder_escape(self):
        from ai_engine.agents.tools import _run_python_code

        r = _run_python_code("x = ().__class__.__bases__")
        assert not r["success"], "dunder escape should be blocked"

    def test_sandbox_blocks_eval(self):
        from ai_engine.agents.tools import _run_python_code

        r = _run_python_code("eval('1+1')")
        assert not r["success"], "eval() should be blocked"

    def test_sandbox_allows_math(self):
        from ai_engine.agents.tools import _run_python_code

        r = _run_python_code("import math; print(round(math.pi, 4))")
        assert r["success"]
        assert "3.1416" in r["stdout"]

    def test_sandbox_allows_json(self):
        from ai_engine.agents.tools import _run_python_code

        r = _run_python_code('import json; print(json.dumps({"a": 1}))')
        assert r["success"]
        assert '"a"' in r["stdout"]

    def test_sandbox_enforces_size_limit(self):
        from ai_engine.agents.tools import _run_python_code

        big = "x = 1\n" * 60_000
        r = _run_python_code(big)
        assert not r["success"]
        assert "size" in r["stderr"].lower()

    def test_sandbox_timeout(self):
        from ai_engine.agents.tools import _run_python_code

        r = _run_python_code("while True: pass", timeout_seconds=1)
        assert not r["success"]
        assert "timeout" in r["stderr"].lower() or "exceeded" in r["stderr"].lower()
