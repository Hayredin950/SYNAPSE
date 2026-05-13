"""
backend.apps.billing.signals
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Django signals for billing — auto-create subscription and referral code on signup.

Phase 9.3 — Growth & Iteration
"""

import structlog

from django.db.models.signals import post_save
from django.dispatch import receiver

logger = structlog.get_logger(__name__)


@receiver(post_save, sender="users.User")
def create_user_subscription(sender, instance, created: bool, **kwargs) -> None:
    """Auto-create a free Subscription when a new user signs up."""
    if not created:
        return
    try:
        from apps.billing.models import Subscription

        Subscription.objects.get_or_create(
            user=instance,
            defaults={"plan": "free", "status": "active"},
        )
        logger.info("subscription_created", user=instance.email, plan="free")
    except Exception as exc:
        logger.error(
            "subscription_creation_failed", user=instance.email, error=str(exc)
        )


@receiver(post_save, sender="users.User")
def create_user_referral_code(sender, instance, created: bool, **kwargs) -> None:
    """Auto-create a referral code when a new user signs up."""
    if not created:
        return
    try:
        from apps.billing.models import ReferralCode

        if not ReferralCode.objects.filter(owner=instance).exists():
            ReferralCode.generate(instance)
            logger.info("referral_code_created", user=instance.email)
    except Exception as exc:
        logger.error(
            "referral_code_creation_failed", user=instance.email, error=str(exc)
        )
