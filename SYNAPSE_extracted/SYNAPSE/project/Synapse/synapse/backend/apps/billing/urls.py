"""
backend.apps.billing.urls
~~~~~~~~~~~~~~~~~~~~~~~~~~~
URL routing for billing, referrals, and feedback.

Phase 9.3 — Growth & Iteration

Mounted at: /api/v1/billing/
"""

from django.urls import path

from . import views

urlpatterns = [
    # Public
    path("pricing/", views.pricing, name="billing-pricing"),
    path("webhook/", views.WebhookView.as_view(), name="billing-webhook"),
    path("feedback/", views.FeedbackView.as_view(), name="billing-feedback"),
    # Authenticated
    path(
        "subscription/", views.SubscriptionView.as_view(), name="billing-subscription"
    ),
    path("checkout/", views.CheckoutView.as_view(), name="billing-checkout"),
    path("portal/", views.PortalView.as_view(), name="billing-portal"),
    path("cancel/", views.CancelView.as_view(), name="billing-cancel"),
    path("invoices/", views.InvoiceListView.as_view(), name="billing-invoices"),
    path("usage/", views.UsageView.as_view(), name="billing-usage"),
    path("referral/", views.ReferralView.as_view(), name="billing-referral"),
]
