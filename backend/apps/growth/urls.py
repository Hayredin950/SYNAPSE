"""
backend.apps.growth.urls
~~~~~~~~~~~~~~~~~~~~~~~~~
Mounted at: /api/v1/growth/
"""

from django.urls import path

from . import views

urlpatterns = [
    path("feedback/", views.FeedbackView.as_view(), name="growth-feedback"),
    path("usage/", views.UsageView.as_view(), name="growth-usage"),
    path("referral/", views.ReferralView.as_view(), name="growth-referral"),
]
