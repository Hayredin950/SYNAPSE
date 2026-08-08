"""
backend.apps.growth.referrals
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Referral program logic — code generation, use tracking, reward granting.

Reward: bonus monthly quota for the referrer, granted immediately when the
referee signs up. There is no payment step to wait for — the app is free.
"""

from __future__ import annotations

import structlog

logger = structlog.get_logger(__name__)


def get_or_create_referral_code(user) -> str:
    """Get or create a referral code for the user. Returns the code string."""
    from apps.growth.models import ReferralCode

    try:
        return ReferralCode.objects.get(owner=user).code
    except ReferralCode.DoesNotExist:
        code_obj = ReferralCode.generate(user)
        logger.info("referral_code_created", user=user.email, code=code_obj.code)
        return code_obj.code


def use_referral_code(referee_user, code: str) -> bool:
    """
    Apply a referral code at signup.

    Returns True if the code was valid and applied. The referrer's quota bonus
    is derived from ReferralCode.uses, so incrementing it here IS the reward —
    see apps.core.quotas.get_referral_bonus.
    """
    from apps.growth.models import ReferralCode, ReferralUse

    try:
        code_obj = ReferralCode.objects.get(code=code.upper().strip())
    except ReferralCode.DoesNotExist:
        logger.warning("referral_code_not_found", code=code)
        return False

    # Can't refer yourself
    if code_obj.owner == referee_user:
        logger.warning("referral_self_use", user=referee_user.email)
        return False

    # One referral per referee
    if ReferralUse.objects.filter(referee=referee_user).exists():
        logger.warning("referral_already_used", user=referee_user.email)
        return False

    if not code_obj.is_valid:
        logger.warning("referral_max_uses_reached", code=code)
        return False

    ReferralUse.objects.create(code=code_obj, referee=referee_user, reward_given=True)
    code_obj.uses += 1
    code_obj.save(update_fields=["uses"])

    logger.info(
        "referral_code_used",
        referee=referee_user.email,
        referrer=code_obj.owner.email,
        referrer_uses=code_obj.uses,
    )
    return True
