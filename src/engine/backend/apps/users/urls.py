from rest_framework_simplejwt.views import TokenRefreshView

from django.urls import path

from . import github_views, mfa_views, onboarding_views, views
from .api_key_views import APIKeyListCreateView, APIKeyRevokeView

urlpatterns = [
    # TASK-605-B4: API Key management
    path("keys/", APIKeyListCreateView.as_view(), name="apikey-list-create"),
    path("keys/<uuid:pk>/", APIKeyRevokeView.as_view(), name="apikey-revoke"),
    path("register/", views.RegisterView.as_view(), name="auth-register"),
    path("login/", views.CustomTokenObtainPairView.as_view(), name="auth-login"),
    path("logout/", views.logout_view, name="auth-logout"),
    path("token/refresh/", TokenRefreshView.as_view(), name="auth-token-refresh"),
    path("me/", views.MeView.as_view(), name="auth-me"),
    path("me/preferences/", views.update_preferences, name="auth-preferences"),
    path("me/digest/", views.digest_preferences, name="auth-digest"),
    path("ai-keys/", views.ai_keys_view, name="user-ai-keys"),
    # ── Password Reset ──────────────────────────────────────────────────────────
    path(
        "password-reset/", views.password_reset_request, name="password-reset-request"
    ),
    path(
        "password-reset/confirm/",
        views.password_reset_confirm,
        name="password-reset-confirm",
    ),
    # ── Email Verification ──────────────────────────────────────────────────────
    path("verify-email/", views.verify_email, name="verify-email"),
    path(
        "verify-email/resend/",
        views.resend_verification_email,
        name="verify-email-resend",
    ),
    # ── Google OAuth ────────────────────────────────────────────────────────────
    path("google/", views.google_auth, name="google-auth"),
    # ── GitHub OAuth ────────────────────────────────────────────────────────────
    path("github/", github_views.github_auth, name="github-auth"),
    path("github/callback/", github_views.github_callback, name="github-callback"),
    path(
        "github/disconnect/", github_views.github_disconnect, name="github-disconnect"
    ),
    # ── MFA ─────────────────────────────────────────────────────────────────────
    path("mfa/setup/", mfa_views.mfa_setup, name="mfa-setup"),
    path("mfa/setup/confirm/", mfa_views.mfa_setup_confirm, name="mfa-setup-confirm"),
    path("mfa/verify/", mfa_views.mfa_verify, name="mfa-verify"),
    path("mfa/verify-backup/", mfa_views.mfa_verify_backup, name="mfa-verify-backup"),
    path("mfa/disable/", mfa_views.mfa_disable, name="mfa-disable"),
    path("mfa/status/", mfa_views.mfa_status, name="mfa-status"),
    # ── Onboarding ───────────────────────────────────────────────────────────────
    path(
        "onboarding/status/",
        onboarding_views.onboarding_status,
        name="onboarding-status",
    ),
    path(
        "onboarding/start/", onboarding_views.onboarding_start, name="onboarding-start"
    ),
    path(
        "onboarding/steps/<int:step>/complete/",
        onboarding_views.onboarding_complete_step,
        name="onboarding-step",
    ),
    path(
        "onboarding/finish/",
        onboarding_views.onboarding_finish,
        name="onboarding-finish",
    ),
    path("activity/", views.user_activity_heatmap, name="user-activity"),
]
