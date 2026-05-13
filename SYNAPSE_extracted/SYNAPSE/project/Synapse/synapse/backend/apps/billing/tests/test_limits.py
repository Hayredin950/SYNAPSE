"""
TASK-003-T1 — Unit tests for plan limit enforcement.
"""

from unittest.mock import MagicMock, patch

from apps.billing.limits import (
    check_plan_limit,
    get_plan_limit,
    get_user_plan,
    plan_limit_response,
    user_has_feature,
)

from django.core.exceptions import PermissionDenied
from django.test import TestCase


def _make_user(plan="free", status="active"):
    user = MagicMock()
    user.email = "test@example.com"
    sub = MagicMock()
    sub.plan = plan
    sub.is_active = status in ("active", "trialing")
    user.subscription = sub
    return user


class TestGetUserPlan(TestCase):
    def test_free_plan(self):
        user = _make_user("free")
        self.assertEqual(get_user_plan(user), "free")

    def test_pro_plan(self):
        user = _make_user("pro")
        self.assertEqual(get_user_plan(user), "pro")

    def test_enterprise_plan(self):
        user = _make_user("enterprise")
        self.assertEqual(get_user_plan(user), "enterprise")

    def test_inactive_subscription_falls_back_to_free(self):
        user = _make_user("pro", status="canceled")
        self.assertEqual(get_user_plan(user), "free")

    def test_missing_subscription_falls_back_to_free(self):
        user = MagicMock()
        user.email = "x@x.com"
        del user.subscription  # AttributeError
        self.assertEqual(get_user_plan(user), "free")


class TestGetPlanLimit(TestCase):
    def test_free_ai_queries(self):
        self.assertEqual(get_plan_limit("free", "ai_queries"), 50)

    def test_pro_ai_queries_unlimited(self):
        self.assertEqual(get_plan_limit("pro", "ai_queries"), -1)

    def test_free_documents(self):
        self.assertEqual(get_plan_limit("free", "documents"), 10)

    def test_unknown_resource_returns_zero(self):
        self.assertEqual(get_plan_limit("free", "nonexistent"), 0)


class TestUserHasFeature(TestCase):
    def test_free_no_semantic_search(self):
        user = _make_user("free")
        self.assertFalse(user_has_feature(user, "semantic_search"))

    def test_pro_has_semantic_search(self):
        user = _make_user("pro")
        self.assertTrue(user_has_feature(user, "semantic_search"))

    def test_pro_no_teams(self):
        user = _make_user("pro")
        self.assertFalse(user_has_feature(user, "teams"))

    def test_enterprise_has_teams(self):
        user = _make_user("enterprise")
        self.assertTrue(user_has_feature(user, "teams"))

    def test_enterprise_has_sso(self):
        user = _make_user("enterprise")
        self.assertTrue(user_has_feature(user, "sso"))

    def test_unknown_feature_returns_false(self):
        user = _make_user("pro")
        self.assertFalse(user_has_feature(user, "unknown_feature"))


class TestCheckPlanLimit(TestCase):
    def test_unlimited_plan_never_raises(self):
        user = _make_user("pro")
        # Should not raise even at very high usage
        check_plan_limit(user, "ai_queries", current_usage=99999)

    def test_free_under_limit_passes(self):
        user = _make_user("free")
        check_plan_limit(user, "ai_queries", current_usage=49)

    def test_free_at_limit_raises(self):
        user = _make_user("free")
        with self.assertRaises(PermissionDenied) as ctx:
            check_plan_limit(user, "ai_queries", current_usage=50)
        exc = ctx.exception
        self.assertEqual(exc.error_code, "plan_limit_exceeded")
        self.assertEqual(exc.resource, "ai_queries")
        self.assertEqual(exc.plan, "free")
        self.assertEqual(exc.limit, 50)
        self.assertEqual(exc.usage, 50)

    def test_free_over_limit_raises(self):
        user = _make_user("free")
        with self.assertRaises(PermissionDenied):
            check_plan_limit(user, "documents", current_usage=11)

    def test_error_code_on_exception(self):
        user = _make_user("free")
        try:
            check_plan_limit(user, "automations", current_usage=5)
            self.fail("Expected PermissionDenied")
        except PermissionDenied as exc:
            self.assertEqual(exc.error_code, "plan_limit_exceeded")
            self.assertIn("upgrade", str(exc).lower())


class TestPlanLimitResponse(TestCase):
    def test_response_shape(self):
        user = _make_user("free")
        try:
            check_plan_limit(user, "ai_queries", current_usage=50)
        except PermissionDenied as exc:
            resp = plan_limit_response(exc)
            self.assertEqual(resp["error_code"], "plan_limit_exceeded")
            self.assertEqual(resp["resource"], "ai_queries")
            self.assertEqual(resp["plan"], "free")
            self.assertEqual(resp["limit"], 50)
            self.assertEqual(resp["usage"], 50)
            self.assertIn("upgrade_url", resp)
