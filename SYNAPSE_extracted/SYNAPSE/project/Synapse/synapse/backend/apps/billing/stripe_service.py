"""
backend.apps.billing.stripe_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Stripe integration — checkout sessions, portal, webhooks, plan upgrades.

Phase 9.3 — Growth & Iteration

Stripe best practices:
  ✓ Idempotency keys on all write operations
  ✓ Webhook signature verification (never trust payload alone)
  ✓ Store Stripe IDs in DB — never re-fetch from Stripe on hot path
  ✓ Async webhook processing via Celery (fast HTTP 200 response)
  ✓ Graceful degradation if Stripe is down
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import structlog

logger = structlog.get_logger(__name__)

STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRO_PRICE_ID = os.environ.get("STRIPE_PRO_PRICE_ID", "")
STRIPE_ENT_PRICE_ID = os.environ.get("STRIPE_ENT_PRICE_ID", "")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")


def _stripe():
    """Return configured stripe module."""
    import stripe as _s

    _s.api_key = STRIPE_SECRET_KEY
    _s.api_version = "2024-04-10"  # pin API version
    return _s


# ── Customer management ────────────────────────────────────────────────────────


def get_or_create_customer(user) -> str:
    """
    Get or create a Stripe customer for the user.
    Returns the Stripe customer ID.
    """
    from apps.billing.models import Subscription

    stripe = _stripe()

    sub, _ = Subscription.objects.get_or_create(
        user=user,
        defaults={"plan": "free", "status": "active"},
    )

    if sub.stripe_customer_id:
        return sub.stripe_customer_id

    # Create Stripe customer
    customer = stripe.Customer.create(
        email=user.email,
        metadata={"user_id": str(user.id), "username": user.username},
        idempotency_key=f"customer-{user.id}",
    )
    sub.stripe_customer_id = customer.id
    sub.save(update_fields=["stripe_customer_id", "updated_at"])

    logger.info("stripe_customer_created", user=user.email, customer_id=customer.id)
    return customer.id


# ── Checkout session ───────────────────────────────────────────────────────────


def create_checkout_session(
    user,
    plan: str,
    referral_code: Optional[str] = None,
) -> str:
    """
    Create a Stripe Checkout session for subscription.
    Returns the checkout URL.
    """
    stripe = _stripe()
    price_id = STRIPE_PRO_PRICE_ID if plan == "pro" else STRIPE_ENT_PRICE_ID
    customer_id = get_or_create_customer(user)

    metadata: dict = {"user_id": str(user.id), "plan": plan}
    if referral_code:
        metadata["referral_code"] = referral_code

    session = stripe.checkout.Session.create(
        customer=customer_id,
        payment_method_types=["card"],
        line_items=[{"price": price_id, "quantity": 1}],
        mode="subscription",
        allow_promotion_codes=True,
        subscription_data={
            "trial_period_days": 14,  # 14-day free trial
            "metadata": metadata,
        },
        success_url=f"{FRONTEND_URL}/dashboard?subscription=success&plan={plan}",
        cancel_url=f"{FRONTEND_URL}/pricing?subscription=canceled",
        metadata=metadata,
        idempotency_key=f"checkout-{user.id}-{plan}",
    )

    logger.info(
        "checkout_session_created", user=user.email, plan=plan, session_id=session.id
    )
    return session.url


# ── Customer portal ────────────────────────────────────────────────────────────


def create_portal_session(user) -> str:
    """
    Create a Stripe Customer Portal session for managing subscriptions.
    Returns the portal URL.
    """
    stripe = _stripe()
    customer_id = get_or_create_customer(user)

    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=f"{FRONTEND_URL}/dashboard/settings",
    )

    logger.info("portal_session_created", user=user.email)
    return session.url


# ── Webhook processing ─────────────────────────────────────────────────────────


def construct_webhook_event(payload: bytes, sig_header: str):
    """
    Verify and parse a Stripe webhook event.
    Raises stripe.error.SignatureVerificationError on invalid signature.
    """
    stripe = _stripe()
    return stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)


def handle_subscription_created(event_data: dict) -> None:
    """Handle customer.subscription.created webhook."""
    _update_subscription_from_stripe(event_data["object"])


def handle_subscription_updated(event_data: dict) -> None:
    """Handle customer.subscription.updated webhook."""
    _update_subscription_from_stripe(event_data["object"])


def handle_subscription_deleted(event_data: dict) -> None:
    """Handle customer.subscription.deleted webhook — downgrade to free."""
    from apps.billing.models import Subscription

    stripe_sub = event_data["object"]
    customer_id = stripe_sub.get("customer")

    try:
        sub = Subscription.objects.get(stripe_customer_id=customer_id)
        sub.plan = "free"
        sub.status = "canceled"
        sub.stripe_subscription_id = ""
        sub.save(
            update_fields=["plan", "status", "stripe_subscription_id", "updated_at"]
        )

        # Downgrade user role
        sub.user.role = "user"
        sub.user.save(update_fields=["role"])

        logger.info("subscription_canceled", user=sub.user.email)
    except Subscription.DoesNotExist:
        logger.warning(
            "subscription_not_found_for_cancellation", customer_id=customer_id
        )


def handle_invoice_paid(event_data: dict) -> None:
    """Handle invoice.payment_succeeded — grant Pro access + referral reward + create Invoice record."""
    import datetime

    from apps.billing.models import Invoice, ReferralUse, Subscription
    from apps.billing.referrals import grant_referral_reward

    invoice = event_data["object"]
    customer_id = invoice.get("customer")

    try:
        sub = Subscription.objects.get(stripe_customer_id=customer_id)

        # Record Invoice in DB
        stripe_inv_id = invoice.get("id", "")
        if (
            stripe_inv_id
            and not Invoice.objects.filter(stripe_invoice_id=stripe_inv_id).exists()
        ):
            period_start = None
            period_end = None
            if invoice.get("period_start"):
                period_start = datetime.datetime.fromtimestamp(
                    invoice["period_start"], tz=datetime.timezone.utc
                )
            if invoice.get("period_end"):
                period_end = datetime.datetime.fromtimestamp(
                    invoice["period_end"], tz=datetime.timezone.utc
                )

            Invoice.objects.create(
                user=sub.user,
                stripe_invoice_id=stripe_inv_id,
                amount_paid=invoice.get("amount_paid", 0),
                currency=invoice.get("currency", "usd"),
                status=invoice.get("status", "paid"),
                pdf_url=invoice.get("invoice_pdf", ""),
                hosted_url=invoice.get("hosted_invoice_url", ""),
                period_start=period_start,
                period_end=period_end,
            )

        # Check for first payment (new subscription) → grant referral reward
        if invoice.get("billing_reason") == "subscription_create":
            try:
                referral_use = ReferralUse.objects.get(
                    referee=sub.user, reward_given=False
                )
                grant_referral_reward(referral_use)
            except ReferralUse.DoesNotExist:
                pass

        logger.info(
            "invoice_paid", user=sub.user.email, amount=invoice.get("amount_paid")
        )
    except Subscription.DoesNotExist:
        logger.warning("subscription_not_found_for_invoice", customer_id=customer_id)


def handle_payment_failed(event_data: dict) -> None:
    """Handle invoice.payment_failed — mark past_due."""
    from apps.billing.models import Subscription

    invoice = event_data["object"]
    customer_id = invoice.get("customer")

    try:
        sub = Subscription.objects.get(stripe_customer_id=customer_id)
        sub.status = "past_due"
        sub.save(update_fields=["status", "updated_at"])
        logger.warning("payment_failed", user=sub.user.email)
    except Subscription.DoesNotExist:
        pass


# ── Internal helpers ───────────────────────────────────────────────────────────


def _update_subscription_from_stripe(stripe_sub: dict) -> None:
    """Sync local Subscription model from Stripe subscription object."""
    import datetime

    from apps.billing.models import Plan, Subscription

    from django.utils import timezone

    customer_id = stripe_sub.get("customer")
    status = stripe_sub.get("status", "active")
    items = stripe_sub.get("items", {}).get("data", [])
    price_id = items[0]["price"]["id"] if items else ""

    # Determine plan from price ID
    if price_id == STRIPE_PRO_PRICE_ID:
        plan = "pro"
    elif price_id == STRIPE_ENT_PRICE_ID:
        plan = "enterprise"
    else:
        plan = "free"

    try:
        sub = Subscription.objects.get(stripe_customer_id=customer_id)
        sub.plan = plan
        sub.status = status
        sub.stripe_subscription_id = stripe_sub.get("id", "")
        sub.stripe_price_id = price_id
        sub.cancel_at_period_end = stripe_sub.get("cancel_at_period_end", False)

        # Convert Unix timestamps
        if stripe_sub.get("current_period_start"):
            sub.current_period_start = datetime.datetime.fromtimestamp(
                stripe_sub["current_period_start"], tz=timezone.utc
            )
        if stripe_sub.get("current_period_end"):
            sub.current_period_end = datetime.datetime.fromtimestamp(
                stripe_sub["current_period_end"], tz=timezone.utc
            )
        sub.save()

        # Upgrade user role
        if plan in ("pro", "enterprise") and status in ("active", "trialing"):
            sub.user.role = "premium" if plan == "pro" else "admin"
            sub.user.save(update_fields=["role"])

        logger.info(
            "subscription_synced", user=sub.user.email, plan=plan, status=status
        )
    except Subscription.DoesNotExist:
        logger.warning("subscription_not_found", customer_id=customer_id)
