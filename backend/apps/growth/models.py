"""
backend.apps.growth.models
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Growth models — referral codes and user feedback.

SYNAPSE is free to use. Referrals do not unlock paid plans; they raise the
referrer's monthly quota ceiling (see apps.core.quotas.get_referral_bonus).
"""

from __future__ import annotations

import secrets
import string
import uuid

from django.conf import settings
from django.db import models


class ReferralCode(models.Model):
    """
    User referral codes — referrer earns bonus monthly quota per signup.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="referral_code"
    )
    code = models.CharField(max_length=12, unique=True, db_index=True)
    uses = models.PositiveIntegerField(default=0)
    max_uses = models.PositiveIntegerField(default=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "growth_referral_codes"
        verbose_name = "Referral Code"

    def __str__(self):
        return f"{self.code} ({self.owner.email})"

    @classmethod
    def generate(cls, owner) -> "ReferralCode":
        """Generate a unique 8-character referral code for the user."""
        alphabet = string.ascii_uppercase + string.digits
        for _ in range(10):
            code = "".join(secrets.choice(alphabet) for _ in range(8))
            if not cls.objects.filter(code=code).exists():
                return cls.objects.create(owner=owner, code=code)
        raise ValueError("Could not generate unique referral code")

    @property
    def is_valid(self) -> bool:
        return self.uses < self.max_uses


class ReferralUse(models.Model):
    """Tracks when a new user signs up via a referral code."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.ForeignKey(
        ReferralCode, on_delete=models.CASCADE, related_name="referral_uses"
    )
    referee = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="referred_by"
    )
    reward_given = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "growth_referral_uses"
        verbose_name = "Referral Use"


class UserFeedback(models.Model):
    """In-app NPS feedback and feature requests."""

    class FeedbackType(models.TextChoices):
        NPS = "nps", "NPS Score"
        BUG = "bug", "Bug Report"
        FEATURE = "feature", "Feature Request"
        GENERAL = "general", "General Feedback"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="feedback",
    )
    type = models.CharField(
        max_length=20, choices=FeedbackType.choices, default=FeedbackType.GENERAL
    )
    nps_score = models.PositiveSmallIntegerField(null=True, blank=True)  # 0–10
    message = models.TextField(max_length=2000, blank=True)
    page_url = models.URLField(max_length=500, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "growth_user_feedback"
        verbose_name = "User Feedback"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.type} from {self.user.email if self.user else 'anonymous'}"
