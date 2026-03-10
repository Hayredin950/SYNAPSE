"""
backend.apps.billing.views
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
REST API views for billing, referrals, and feedback.

Phase 9.3 — Growth & Iteration

Endpoints mounted at /api/v1/billing/
"""

from __future__ import annotations

import logging

import structlog

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

logger = structlog.get_logger(__name__)


# ── Pricing plans (public) ────────────────────────────────────────────────────

PLANS = {
    "free": {
        "name": "Free",
        "price": 0,
        "currency": "usd",
        "interval": None,
        "features": [
            "50 AI queries/month",
            "10 documents/month",
            "Tech feed (last 7 days)",
            "GitHub radar (public repos)",
            "Basic search",
            "5 automation workflows",
        ],
        "limits": {
            "ai_queries": 50,
            "documents": 10,
            "bookmarks": 100,
            "automations": 5,
        },
    },
    "pro": {
        "name": "Pro",
        "price": 1900,  # cents
        "currency": "usd",
        "interval": "month",
        "trial_days": 14,
        "features": [
            "Unlimited AI queries",
            "Unlimited documents",
            "Full tech feed history",
            "GitHub radar (private repos)",
            "Semantic search",
            "Unlimited automations",
            "Google Drive + S3 integration",
            "Priority support",
        ],
        "limits": {
            "ai_queries": -1,  # unlimited
            "documents": -1,
            "bookmarks": -1,
            "automations": -1,
        },
    },
    "enterprise": {
        "name": "Enterprise",
        "price": 9900,
        "currency": "usd",
        "interval": "month",
        "trial_days": 14,
        "features": [
            "Everything in Pro",
            "Team workspaces",
            "SSO / SAML",
            "Custom AI model fine-tuning",
            "Dedicated Slack support",
            "SLA 99.9% uptime",
            "Custom integrations",
            "Audit logs",
        ],
        "limits": {
            "ai_queries": -1,
            "documents": -1,
            "bookmarks": -1,
            "automations": -1,
        },
    },
}


@api_view(["GET"])
@permission_classes([AllowAny])
def pricing(request: Request) -> Response:
    """GET /api/v1/billing/pricing/ — public plan listing."""
    return Response({"plans": PLANS})


# ── Subscription ───────────────────────────────────────────────────────────────


class SubscriptionView(APIView):
    """GET /api/v1/billing/subscription/ — current user's subscription."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        from apps.billing.models import Subscription

        sub, _ = Subscription.objects.get_or_create(
            user=request.user,
            defaults={"plan": "free", "status": "active"},
        )
        return Response(
            {
                "plan": sub.plan,
                "status": sub.status,
                "is_active": sub.is_active,
                "is_pro": sub.is_pro,
                "cancel_at_period_end": sub.cancel_at_period_end,
                "current_period_end": sub.current_period_end,
                "trial_end": sub.trial_end,
            }
        )


class CheckoutView(APIView):
    """POST /api/v1/billing/checkout/ — create Stripe Checkout session."""

    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        plan = request.data.get("plan", "pro")
        referral_code = request.data.get("referral_code")

        if plan not in ("pro", "enterprise"):
            return Response(
                {"error": "Invalid plan. Choose 'pro' or 'enterprise'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            from apps.billing.stripe_service import create_checkout_session

            url = create_checkout_session(request.user, plan, referral_code)
            return Response({"checkout_url": url})
        except Exception as exc:
            logger.error("checkout_session_failed", error=str(exc))
            return Response(
                {"error": "Could not create checkout session. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class PortalView(APIView):
    """POST /api/v1/billing/portal/ — Stripe Customer Portal (manage sub)."""

    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        try:
            from apps.billing.stripe_service import create_portal_session

            url = create_portal_session(request.user)
            return Response({"portal_url": url})
        except Exception as exc:
            logger.error("portal_session_failed", error=str(exc))
            return Response(
                {"error": "Could not open billing portal."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ── Stripe Webhook ────────────────────────────────────────────────────────────


@method_decorator(csrf_exempt, name="dispatch")
class WebhookView(APIView):
    """
    POST /api/v1/billing/webhook/
    Receives Stripe webhook events — signature verified, processed async via Celery.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request: Request) -> Response:
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")
        payload = request.body

        try:
            # Verify Stripe webhook signature
            import stripe

            from django.conf import settings

            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
        except Exception as exc:
            logger.warning("stripe_webhook_invalid_signature", error=str(exc))
            return Response(
                {"error": "Invalid signature."}, status=status.HTTP_400_BAD_REQUEST
            )

        # Dispatch to Celery for async processing (fast 200 response to Stripe)
        from apps.billing.tasks import process_stripe_webhook

        process_stripe_webhook.delay(event["type"], dict(event["data"]))

        logger.info("stripe_webhook_received", event_type=event["type"])
        return Response({"received": True})


# ── Referrals ─────────────────────────────────────────────────────────────────


class CancelView(APIView):
    """POST /api/v1/billing/cancel/ — cancel subscription at period end."""

    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        from apps.billing.models import Subscription

        try:
            sub = Subscription.objects.get(user=request.user)
        except Subscription.DoesNotExist:
            return Response(
                {"error": "No active subscription found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if sub.plan == "free":
            return Response(
                {"error": "You are already on the free plan."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            stripe = __import__("apps.billing.stripe_service", fromlist=["_stripe"])
            import apps.billing.stripe_service as svc

            s = svc._stripe()
            if sub.stripe_subscription_id:
                s.Subscription.modify(
                    sub.stripe_subscription_id,
                    cancel_at_period_end=True,
                )
            sub.cancel_at_period_end = True
            sub.save(update_fields=["cancel_at_period_end", "updated_at"])
            logger.info("subscription_cancel_requested", user=request.user.email)
            return Response(
                {
                    "success": True,
                    "message": "Your subscription will cancel at the end of the current billing period.",
                    "cancel_at_period_end": True,
                    "current_period_end": sub.current_period_end,
                }
            )
        except Exception as exc:
            logger.error("subscription_cancel_failed", error=str(exc))
            return Response(
                {"error": "Could not cancel subscription. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class InvoiceListView(APIView):
    """GET /api/v1/billing/invoices/ — list user's past invoices."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        from apps.billing.models import Invoice

        invoices = Invoice.objects.filter(user=request.user).order_by("-created_at")[
            :24
        ]
        data = [
            {
                "id": str(inv.id),
                "stripe_invoice_id": inv.stripe_invoice_id,
                "amount": inv.amount_paid,
                "amount_display": inv.amount_display,
                "currency": inv.currency,
                "status": inv.status,
                "pdf_url": inv.pdf_url,
                "hosted_url": inv.hosted_url,
                "period_start": inv.period_start,
                "period_end": inv.period_end,
                "created_at": inv.created_at,
            }
            for inv in invoices
        ]
        return Response({"invoices": data})


class UsageView(APIView):
    """GET /api/v1/billing/usage/ — current user's plan usage stats."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        from apps.billing.limits import (
            PLAN_LIMITS,
            _count_usage,
            get_plan_limit,
            get_user_plan,
        )

        plan = get_user_plan(request.user)
        resources = list(PLAN_LIMITS.get(plan, PLAN_LIMITS["free"]).keys())
        usage_data = {}
        for resource in resources:
            limit = get_plan_limit(plan, resource)
            current = _count_usage(request.user, resource)
            usage_data[resource] = {
                "used": current,
                "limit": limit,
                "unlimited": limit == -1,
                "percent": (
                    0 if limit == -1 else round(min(current / limit * 100, 100), 1)
                ),
            }
        return Response({"plan": plan, "usage": usage_data})


class ReferralView(APIView):
    """GET /api/v1/billing/referral/ — get or create referral code."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        from apps.billing.models import ReferralCode
        from apps.billing.referrals import get_or_create_referral_code

        code = get_or_create_referral_code(request.user)
        try:
            ref_obj = ReferralCode.objects.get(owner=request.user)
            referral_url = f"{request.build_absolute_uri('/')[:-1]}/register?ref={code}"
            return Response(
                {
                    "code": code,
                    "uses": ref_obj.uses,
                    "max_uses": ref_obj.max_uses,
                    "referral_url": referral_url,
                    "reward": "1 month Pro for you when your referral subscribes",
                }
            )
        except ReferralCode.DoesNotExist:
            return Response({"code": code})

    def post(self, request: Request) -> Response:
        """POST — apply a referral code (called at signup)."""
        code = request.data.get("code", "").strip()
        if not code:
            return Response(
                {"error": "code is required."}, status=status.HTTP_400_BAD_REQUEST
            )

        from apps.billing.referrals import use_referral_code

        success = use_referral_code(request.user, code)
        if success:
            return Response(
                {
                    "success": True,
                    "message": "Referral code applied! Your referrer will earn 1 month Pro when you subscribe.",
                }
            )
        return Response(
            {"success": False, "error": "Invalid or already used referral code."},
            status=status.HTTP_400_BAD_REQUEST,
        )


# ── Feedback ──────────────────────────────────────────────────────────────────


class FeedbackView(APIView):
    """POST /api/v1/billing/feedback/ — submit NPS or feedback."""

    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        from apps.billing.models import UserFeedback

        feedback_type = request.data.get("type", "general")
        nps_score = request.data.get("nps_score")
        message = request.data.get("message", "").strip()[:2000]
        page_url = request.data.get("page_url", "")[:500]

        if nps_score is not None:
            try:
                nps_score = int(nps_score)
                if not (0 <= nps_score <= 10):
                    return Response({"error": "nps_score must be 0–10."}, status=400)
            except (TypeError, ValueError):
                return Response({"error": "nps_score must be an integer."}, status=400)

        feedback = UserFeedback.objects.create(
            user=request.user if request.user.is_authenticated else None,
            type=feedback_type,
            nps_score=nps_score,
            message=message,
            page_url=page_url,
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:300],
        )

        # Track in analytics
        if request.user.is_authenticated:
            from apps.core.analytics import track

            try:
                from apps.core.analytics import _get_posthog

                ph = _get_posthog()
                if ph:
                    ph.capture(
                        str(request.user.id),
                        "feedback_submitted",
                        {
                            "type": feedback_type,
                            "nps_score": nps_score,
                        },
                    )
            except Exception:
                pass

        logger.info("feedback_received", type=feedback_type, nps_score=nps_score)
        return Response(
            {"success": True, "id": str(feedback.id)}, status=status.HTTP_201_CREATED
        )
