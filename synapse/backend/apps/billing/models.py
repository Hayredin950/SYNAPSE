"""
backend.apps.billing.models
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Stripe billing models — Subscription, Plan, ReferralCode, Feedback.

Phase 9.3 — Growth & Iteration

Plans: Free | Pro ($19/mo) | Enterprise ($99/mo)
"""

from __future__ import annotations

import secrets
import string
import uuid

from django.conf import settings
from django.db import models


class Plan(models.TextChoices):
    FREE = "free", "Free"
    PRO = "pro", "Pro ($19/mo)"
    ENTERPRISE = "enterprise", "Enterprise ($99/mo)"


class Subscription(models.Model):
    """Tracks a user's Stripe subscription state."""

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        TRIALING = "trialing", "Trialing"
        PAST_DUE = "past_due", "Past Due"
        CANCELED = "canceled", "Canceled"
        INCOMPLETE = "incomplete", "Incomplete"
        INCOMPLETE_EXPIRED = "incomplete_expired", "Incomplete Expired"
        UNPAID = "unpaid", "Unpaid"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="subscription"
    )
    plan = models.CharField(max_length=20, choices=Plan.choices, default=Plan.FREE)
    status = models.CharField(
        max_length=30, choices=Status.choices, default=Status.ACTIVE
    )

    # Stripe IDs
    stripe_customer_id = models.CharField(max_length=100, blank=True, db_index=True)
    stripe_subscription_id = models.CharField(max_length=100, blank=True, db_index=True)
    stripe_price_id = models.CharField(max_length=100, blank=True)

    # Billing period
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)
    trial_end = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "billing_subscriptions"
        verbose_name = "Subscription"

    def __str__(self):
        return f"{self.user.email} — {self.plan} ({self.status})"

    @property
    def is_active(self) -> bool:
        return self.status in (self.Status.ACTIVE, self.Status.TRIALING)

    @property
    def is_pro(self) -> bool:
        return self.plan in (Plan.PRO, Plan.ENTERPRISE) and self.is_active

    def cancel(self) -> None:
        """Mark subscription to cancel at period end via Stripe webhook."""
        self.cancel_at_period_end = True
        self.save(update_fields=["cancel_at_period_end", "updated_at"])


class ReferralCode(models.Model):
    """
    User referral codes — 1 month Pro for referrer when referee subscribes.
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
        db_table = "billing_referral_codes"
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
        db_table = "billing_referral_uses"
        verbose_name = "Referral Use"


class Invoice(models.Model):
    """Tracks Stripe invoices for a user."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="invoices"
    )
    stripe_invoice_id = models.CharField(max_length=100, unique=True, db_index=True)
    amount_paid = models.PositiveIntegerField(default=0, help_text="Amount in cents")
    currency = models.CharField(max_length=3, default="usd")
    status = models.CharField(max_length=30, default="paid")
    pdf_url = models.URLField(max_length=500, blank=True)
    hosted_url = models.URLField(max_length=500, blank=True)
    period_start = models.DateTimeField(null=True, blank=True)
    period_end = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "billing_invoices"
        verbose_name = "Invoice"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Invoice {self.stripe_invoice_id} — {self.user.email}"

    @property
    def amount_display(self) -> str:
        """Human-readable amount, e.g. '$19.00'."""
        return f"${self.amount_paid / 100:.2f}"


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
        db_table = "billing_user_feedback"
        verbose_name = "User Feedback"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.type} from {self.user.email if self.user else 'anonymous'}"
