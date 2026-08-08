"""
backend.apps.growth.views
~~~~~~~~~~~~~~~~~~~~~~~~~~
Referral, quota-usage, and feedback endpoints.

Mounted at /api/v1/growth/.
"""

from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView


class UsageView(APIView):
    """GET /api/v1/growth/usage/ — current user's quota usage."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        from apps.core.quotas import get_usage_summary

        summary = get_usage_summary(request.user)

        # Flatten into the shape the UI renders: per-resource used/limit/percent
        usage_data = {}
        for resource, periods in summary.items():
            usage_data[resource] = {
                period: {
                    "used": vals["usage"],
                    "limit": vals["limit"],
                    "unlimited": vals["limit"] == -1,
                    "percent": (
                        0
                        if vals["limit"] == -1
                        else round(min(vals["usage"] / vals["limit"] * 100, 100), 1)
                    ),
                }
                for period, vals in periods.items()
            }

        return Response({"usage": usage_data})


class ReferralView(APIView):
    """GET/POST /api/v1/growth/referral/ — get or apply a referral code."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        from apps.core.quotas import BONUS_PER_REFERRAL, MAX_BONUS_REFERRALS
        from apps.growth.models import ReferralCode
        from apps.growth.referrals import get_or_create_referral_code

        code = get_or_create_referral_code(request.user)
        try:
            ref_obj = ReferralCode.objects.get(owner=request.user)
        except ReferralCode.DoesNotExist:
            return Response({"code": code})

        bonus = ", ".join(f"+{n} {res}" for res, n in BONUS_PER_REFERRAL.items())
        return Response(
            {
                "code": code,
                "uses": ref_obj.uses,
                "max_uses": ref_obj.max_uses,
                "referral_url": (
                    f"{request.build_absolute_uri('/')[:-1]}/register?ref={code}"
                ),
                "reward": (
                    f"Each signup raises your monthly quota ({bonus}), "
                    f"up to {MAX_BONUS_REFERRALS} referrals."
                ),
                "bonus_referrals_counted": min(ref_obj.uses, MAX_BONUS_REFERRALS),
                "bonus_referrals_max": MAX_BONUS_REFERRALS,
            }
        )

    def post(self, request: Request) -> Response:
        """Apply a referral code (called at signup)."""
        code = request.data.get("code", "").strip()
        if not code:
            return Response(
                {"error": "code is required."}, status=status.HTTP_400_BAD_REQUEST
            )

        from apps.growth.referrals import use_referral_code

        if use_referral_code(request.user, code):
            return Response(
                {
                    "success": True,
                    "message": "Referral code applied — your referrer's monthly quota went up.",
                }
            )
        return Response(
            {"success": False, "error": "Invalid or already used referral code."},
            status=status.HTTP_400_BAD_REQUEST,
        )


class FeedbackView(APIView):
    """POST /api/v1/growth/feedback/ — submit NPS or feedback."""

    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        from apps.growth.models import UserFeedback

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

        UserFeedback.objects.create(
            user=request.user if request.user.is_authenticated else None,
            type=feedback_type,
            nps_score=nps_score,
            message=message,
            page_url=page_url,
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:300],
        )

        if request.user.is_authenticated:
            try:
                from apps.core.analytics import _get_posthog

                ph = _get_posthog()
                if ph:
                    ph.capture(
                        str(request.user.id),
                        "feedback_submitted",
                        {"type": feedback_type, "nps_score": nps_score},
                    )
            except Exception:
                pass

        return Response({"success": True}, status=status.HTTP_201_CREATED)
