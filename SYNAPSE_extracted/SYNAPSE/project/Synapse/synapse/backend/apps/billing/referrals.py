"""
backend.apps.billing.referrals
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Referral program logic — code generation, use tracking, reward granting.

Phase 9.3 — Growth & Iteration

Reward: 1 month Pro for referrer when referee makes first payment.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Optional

import structlog

from django.utils import timezone

logger = structlog.get_logger(__name__)


def get_or_create_referral_code(user) -> str:
    """Get or create a referral code for the user. Returns the code string."""
    from apps.billing.models import ReferralCode

    code_obj, created = ReferralCode.objects.get_or_create(
        owner=user,
        defaults={},
    )
    if created:
        # Generate code if new
        import secrets
        import string

        alphabet = string.ascii_uppercase + string.digits
        for _ in range(10):
            code = "".join(secrets.choice(alphabet) for _ in range(8))
            if (
                not ReferralCode.objects.filter(code=code)
                .exclude(pk=code_obj.pk)
                .exists()
            ):
                code_obj.code = code
                code_obj.save(update_fields=["code"])
                break

    logger.info("referral_code_retrieved", user=user.email, code=code_obj.code)
    return code_obj.code


def use_referral_code(referee_user, code: str) -> bool:
    """
    Apply a referral code during signup.
    Returns True if the code was valid and applied successfully.
    """
    from apps.billing.models import ReferralCode, ReferralUse

    try:
        code_obj = ReferralCode.objects.get(code=code.upper().strip())
    except ReferralCode.DoesNotExist:
        logger.warning("referral_code_not_found", code=code)
        return False

    # Can't refer yourself
    if code_obj.owner == referee_user:
        logger.warning("referral_self_use", user=referee_user.email)
        return False

    # Check if already used by this referee
    if ReferralUse.objects.filter(referee=referee_user).exists():
        logger.warning("referral_already_used", user=referee_user.email)
        return False

    # Check max uses
    if not code_obj.is_valid:
        logger.warning("referral_max_uses_reached", code=code)
        return False

    # Record use
    ReferralUse.objects.create(code=code_obj, referee=referee_user)
    code_obj.uses += 1
    code_obj.save(update_fields=["uses"])

    logger.info(
        "referral_code_used", referee=referee_user.email, referrer=code_obj.owner.email
    )
    return True


def grant_referral_reward(referral_use) -> None:
    """
    Grant 1-month Pro to the referrer when the referee makes their first payment.
    """
    from apps.billing.models import Subscription

    referrer = referral_use.code.owner

    try:
        sub = Subscription.objects.get(user=referrer)
        # Extend current period end by 30 days (or set if free)
        if sub.current_period_end and sub.current_period_end > timezone.now():
            sub.current_period_end += timedelta(days=30)
        else:
            sub.current_period_end = timezone.now() + timedelta(days=30)

        # Upgrade to pro if currently free
        if sub.plan == "free":
            sub.plan = "pro"
            sub.status = "active"
            referrer.role = "premium"
            referrer.save(update_fields=["role"])

        sub.save(update_fields=["plan", "status", "current_period_end", "updated_at"])

        referral_use.reward_given = True
        referral_use.save(update_fields=["reward_given"])

        logger.info(
            "referral_reward_granted",
            referrer=referrer.email,
            referee=referral_use.referee.email,
            new_period_end=sub.current_period_end,
        )
    except Subscription.DoesNotExist:
        logger.error("referral_reward_failed_no_subscription", referrer=referrer.email)
