"""
backend.apps.growth.signals
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Auto-create a referral code when a new user signs up.
"""

import structlog

from django.db.models.signals import post_save
from django.dispatch import receiver

logger = structlog.get_logger(__name__)


@receiver(post_save, sender="users.User")
def create_user_referral_code(sender, instance, created: bool, **kwargs) -> None:
    """Auto-create a referral code when a new user signs up."""
    if not created:
        return
    try:
        from apps.growth.models import ReferralCode

        if not ReferralCode.objects.filter(owner=instance).exists():
            ReferralCode.generate(instance)
            logger.info("referral_code_created", user=instance.email)
    except Exception as exc:
        logger.error(
            "referral_code_creation_failed", user=instance.email, error=str(exc)
        )
