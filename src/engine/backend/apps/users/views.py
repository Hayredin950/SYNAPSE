import logging
import os
import uuid

import requests as http_requests
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.core.throttles import APIRateThrottle, RegistrationThrottle

from .firebase_email import send_password_reset_email, send_verification_email
from .models import User
from .serializers import (
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    UserPreferencesSerializer,
    UserProfileSerializer,
    UserRegistrationSerializer,
)


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Extend SimpleJWT login response to include user profile data."""

    def validate(self, attrs):
        data = super().validate(attrs)
        # Append user profile so the frontend can hydrate the auth store
        data["user"] = UserProfileSerializer(self.user).data
        return data


class CustomTokenObtainPairView(TokenObtainPairView):
    """POST /api/v1/auth/login/ — returns {access, refresh, user}."""

    serializer_class = CustomTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            # TASK-203: PostHog server-side login event
            try:
                from apps.core.analytics import track_login

                from .models import User

                email = request.data.get("email", "")
                user = User.objects.filter(email=email).first()
                if user:
                    track_login(user)
            except Exception:
                pass  # Analytics must never block login
        return response


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = [AllowAny]
    throttle_classes = [RegistrationThrottle]
    serializer_class = UserRegistrationSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            user = serializer.save()
        except Exception as exc:
            logger.error("Registration save failed: %s", exc, exc_info=True)
            return Response(
                {"detail": "Registration failed. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # TASK-203: PostHog server-side signup event
        try:
            from apps.core.analytics import track_signup

            track_signup(str(user.id), user.email)
        except Exception:
            pass  # Analytics must never block registration

        # Dev shortcut: when AUTO_VERIFY_EMAIL is True (e.g. Replit env where
        # the console email backend means real emails never arrive), auto-verify
        # the user and issue JWT tokens immediately so they can use the app.
        auto_verify = getattr(settings, "AUTO_VERIFY_EMAIL", False)
        if auto_verify:
            user.email_verified = True
            user.email_verification_token = None
            user.save(update_fields=["email_verified", "email_verification_token"])
            refresh = RefreshToken.for_user(user)
            return Response(
                {
                    "success": True,
                    "message": "Account created! Welcome to SYNAPSE.",
                    "user": {
                        "id": str(user.id),
                        "email": user.email,
                        "username": user.username,
                        "first_name": user.first_name,
                        "email_verified": True,
                    },
                    "tokens": {
                        "access": str(refresh.access_token),
                        "refresh": str(refresh),
                    },
                },
                status=status.HTTP_201_CREATED,
            )

        return Response(
            {
                "success": True,
                "message": "Account created! Please check your email to verify your address.",
                "user": {
                    "id": str(user.id),
                    "email": user.email,
                    "username": user.username,
                    "first_name": user.first_name,
                    "email_verified": False,
                },
                # No tokens issued yet — the user must verify email first.
                # The verify-email endpoint issues tokens on success.
            },
            status=status.HTTP_201_CREATED,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """
    POST /api/v1/auth/logout/
    Blacklists the refresh token if possible, then always returns 200.
    Frontend should clear local state regardless of this response.
    """
    refresh_token = request.data.get("refresh")
    if refresh_token:
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except Exception:
            # Token may already be expired, invalid, or blacklisting not enabled
            # — always return success so frontend can clear local state cleanly
            pass
    return Response({"success": True, "data": {"message": "Logged out successfully."}})


class MeView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserProfileSerializer

    def get_object(self):
        return self.request.user

    def retrieve(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object())
        # Return user data directly (not nested) so frontend authStore can
        # read it straight from response.data
        return Response(serializer.data)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        serializer = self.get_serializer(
            self.get_object(), data=request.data, partial=partial
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"success": True, "data": serializer.data})


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def digest_preferences(request):
    """
    GET  /api/v1/auth/digest/   — return current digest_enabled + digest_day
    PATCH /api/v1/auth/digest/  — update digest_enabled and/or digest_day

    TASK-201: Weekly AI digest preference management.
    """
    from rest_framework import status as drf_status
    from rest_framework.response import Response

    user = request.user

    if request.method == "GET":
        return Response(
            {
                "digest_enabled": user.digest_enabled,
                "digest_day": user.digest_day,
            }
        )

    # PATCH — partial update
    data = request.data
    updated = {}

    if "digest_enabled" in data:
        enabled = data["digest_enabled"]
        if not isinstance(enabled, bool):
            return Response(
                {"error": "digest_enabled must be a boolean."},
                status=drf_status.HTTP_400_BAD_REQUEST,
            )
        user.digest_enabled = enabled
        updated["digest_enabled"] = enabled

    if "digest_day" in data:
        valid_days = [
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
        ]
        day = str(data["digest_day"]).lower()
        if day not in valid_days:
            return Response(
                {"error": f"digest_day must be one of: {', '.join(valid_days)}."},
                status=drf_status.HTTP_400_BAD_REQUEST,
            )
        user.digest_day = day
        updated["digest_day"] = day

    if not updated:
        return Response(
            {"error": "Provide digest_enabled and/or digest_day."},
            status=drf_status.HTTP_400_BAD_REQUEST,
        )

    user.save(update_fields=list(updated.keys()))
    return Response(
        {
            "digest_enabled": user.digest_enabled,
            "digest_day": user.digest_day,
        }
    )


@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def update_preferences(request):
    serializer = UserPreferencesSerializer(
        request.user, data=request.data, partial=True
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response({"success": True, "data": serializer.data})


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def ai_keys_view(request):
    """
    GET  /api/v1/users/ai-keys/ — check which keys are configured for this user
    POST /api/v1/users/ai-keys/ — save encrypted keys to user preferences
    Keys are stored in user.preferences JSON field and used by the AI engine and scrapers.
    """
    if request.method == "GET":
        prefs = getattr(request.user, "preferences", {}) or {}
        gemini_ok = bool(prefs.get("gemini_api_key"))
        openrouter_ok = bool(prefs.get("openrouter_api_key"))
        scitely_ok = bool(prefs.get("scitely_api_key"))
        github_ok = bool(prefs.get("github_token"))
        x_api_ok = bool(prefs.get("x_api_key"))

        # Check .env fallback keys (server-wide defaults)
        from django.conf import settings

        env_gemini = bool(os.environ.get("GEMINI_API_KEY"))
        env_openrouter = bool(os.environ.get("OPENROUTER_API_KEY"))
        env_scitely = bool(os.environ.get("SCITELY_API_KEY"))
        # New providers (Apr 2026): server-side keys for the unified LLM factory.
        env_ai_gateway = bool(os.environ.get("AI_GATEWAY_API_KEY"))
        env_groq = bool(os.environ.get("GROQ_API_KEY"))
        env_github = bool(os.environ.get("GITHUB_TOKEN"))
        env_x_api = bool(
            os.environ.get("X_API_KEY") or os.environ.get("TWITTER_BEARER_TOKEN")
        )

        warnings = []
        if not github_ok and not env_github:
            warnings.append(
                {
                    "key": "github_token",
                    "label": "GitHub",
                    "severity": "warning",
                    "message": "No GitHub token set. Using trending page (free, no auth) + unauthenticated API (60 req/hr). Set your token for richer results and 5000 req/hr.",
                }
            )
        elif not github_ok and env_github:
            warnings.append(
                {
                    "key": "github_token",
                    "label": "GitHub",
                    "severity": "info",
                    "message": "Using shared GitHub token. Set your own in Settings for higher rate limits.",
                }
            )

        # An AI key is "configured" if EITHER the user has set their own key
        # OR the server has a usable key in env (any of: AI Gateway, Groq,
        # Scitely, OpenRouter, Gemini).
        any_ai_user_key = gemini_ok or openrouter_ok or scitely_ok
        any_ai_env_key = (
            env_ai_gateway
            or env_groq
            or env_scitely
            or env_openrouter
            or env_gemini
        )

        if not any_ai_user_key and not any_ai_env_key:
            warnings.append(
                {
                    "key": "ai",
                    "label": "AI Chat & Summarization",
                    "severity": "error",
                    "message": "No AI API key configured. AI chat, summarization, and agents are unavailable. Add a key in Settings.",
                }
            )
        elif not any_ai_user_key:
            warnings.append(
                {
                    "key": "ai",
                    "label": "AI Chat & Summarization",
                    "severity": "info",
                    "message": "Using the shared server AI key. Set your own key in Settings for dedicated access.",
                }
            )

        if not x_api_ok and not env_x_api:
            warnings.append(
                {
                    "key": "x_api_key",
                    "label": "X/Twitter",
                    "severity": "info",
                    "message": "Using Mastodon fediverse as tweet source (no API key needed). Add an X/Twitter API key in Settings for native X posts.",
                }
            )
        elif not x_api_ok and env_x_api:
            warnings.append(
                {
                    "key": "x_api_key",
                    "label": "X/Twitter",
                    "severity": "info",
                    "message": "Using shared X/Twitter key. Set your own in Settings for dedicated access.",
                }
            )

        return Response(
            {
                "gemini_configured": gemini_ok,
                "openrouter_configured": openrouter_ok,
                "scitely_configured": scitely_ok,
                "github_configured": github_ok,
                "x_api_configured": x_api_ok,
                # any_configured = at least one usable AI key is in scope
                # (user-supplied OR server env). The frontend banner uses
                # this to decide whether to nag the user about missing keys.
                "any_configured": any_ai_user_key or any_ai_env_key,
                # Surface the new server-side providers so the UI can show
                # a friendlier "Powered by …" hint if it wants to.
                "ai_gateway_env_configured": env_ai_gateway,
                "groq_env_configured": env_groq,
                "warnings": warnings,
            }
        )

    # POST — save keys
    prefs = getattr(request.user, "preferences", {}) or {}
    if not isinstance(prefs, dict):
        prefs = {}

    gemini_key = request.data.get("gemini_api_key", "").strip()
    openrouter_key = request.data.get("openrouter_api_key", "").strip()
    scitely_key = request.data.get("scitely_api_key", "").strip()
    github_token = request.data.get("github_token", "").strip()
    x_api_key = request.data.get("x_api_key", "").strip()

    # Basic format validation — reject obviously invalid keys
    if gemini_key:
        if len(gemini_key) < 10 or len(gemini_key) > 512:
            return Response(
                {"success": False, "error": "Invalid Gemini API key format."},
                status=400,
            )
        prefs["gemini_api_key"] = gemini_key
    if openrouter_key:
        if len(openrouter_key) < 10 or len(openrouter_key) > 512:
            return Response(
                {"success": False, "error": "Invalid OpenRouter API key format."},
                status=400,
            )
        prefs["openrouter_api_key"] = openrouter_key
    if scitely_key:
        if len(scitely_key) < 10 or len(scitely_key) > 512:
            return Response(
                {"success": False, "error": "Invalid Scitely API key format."},
                status=400,
            )
        prefs["scitely_api_key"] = scitely_key
    if github_token:
        if len(github_token) < 10 or len(github_token) > 512:
            return Response(
                {"success": False, "error": "Invalid GitHub token format."}, status=400
            )
        prefs["github_token"] = github_token
    if x_api_key:
        if len(x_api_key) < 10 or len(x_api_key) > 512:
            return Response(
                {"success": False, "error": "Invalid X/Twitter API key format."},
                status=400,
            )
        prefs["x_api_key"] = x_api_key

    request.user.preferences = prefs
    request.user.save(update_fields=["preferences"])

    return Response(
        {
            "success": True,
            "gemini_configured": bool(prefs.get("gemini_api_key")),
            "openrouter_configured": bool(prefs.get("openrouter_api_key")),
            "scitely_configured": bool(prefs.get("scitely_api_key")),
            "github_configured": bool(prefs.get("github_token")),
            "x_api_configured": bool(prefs.get("x_api_key")),
        }
    )


# ── Password Reset ─────────────────────────────────────────────────────────────


@api_view(["POST"])
@permission_classes([AllowAny])
def password_reset_request(request):
    """
    POST /api/v1/auth/password-reset/
    Accepts an email and sends a password reset link.
    Always returns 200 to avoid user enumeration.
    """
    serializer = PasswordResetRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    email = serializer.validated_data["email"]

    try:
        user = User.objects.get(email=email)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:3000")
        reset_url = f"{frontend_url}/reset-password?uid={uid}&token={token}"

        # Send via Firebase (free) with Django fallback
        send_password_reset_email(user, reset_url)
    except User.DoesNotExist:
        pass  # Silently ignore — don't leak whether email exists

    return Response(
        {
            "success": True,
            "message": "If an account with that email exists, a reset link has been sent.",
        }
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def password_reset_confirm(request):
    """
    POST /api/v1/auth/password-reset/confirm/
    Validates uid + token and sets new password.
    """
    serializer = PasswordResetConfirmSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    user = serializer.validated_data["user"]
    user.set_password(serializer.validated_data["new_password"])
    user.save(update_fields=["password"])

    return Response(
        {
            "success": True,
            "message": "Password reset successfully. You can now sign in with your new password.",
        }
    )


# ── Email Verification ─────────────────────────────────────────────────────────


# ── Google OAuth ───────────────────────────────────────────────────────────────


@api_view(["GET"])
@permission_classes([AllowAny])
def verify_email(request):
    """
    GET /api/v1/auth/verify-email/?token=<token>
    Verifies an email verification token and activates the account.
    """
    from django.utils import timezone

    token = request.query_params.get("token")
    if not token:
        return Response(
            {"error": "Verification token is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        user = User.objects.get(email_verification_token=token)
    except User.DoesNotExist:
        return Response(
            {"error": "Invalid or expired verification link."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if user.email_verified:
        # Already verified — just return tokens
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "success": True,
                "message": "Email already verified.",
                "tokens": {
                    "access": str(refresh.access_token),
                    "refresh": str(refresh),
                },
            }
        )

    user.email_verified = True
    user.email_verification_token = None
    user.save(update_fields=["email_verified", "email_verification_token"])

    refresh = RefreshToken.for_user(user)
    return Response(
        {
            "success": True,
            "message": "Email verified successfully.",
            "tokens": {"access": str(refresh.access_token), "refresh": str(refresh)},
        }
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def resend_verification_email(request):
    """
    POST /api/v1/auth/verify-email/resend/
    Body: { "email": "user@example.com" }
    Resends the verification email.
    """
    import uuid as _uuid

    from django.conf import settings as django_settings

    email = request.data.get("email", "").strip().lower()
    if not email:
        return Response(
            {"error": "Email is required."}, status=status.HTTP_400_BAD_REQUEST
        )

    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        # Don't leak whether email exists
        return Response(
            {
                "success": True,
                "message": "If that email exists, a verification link has been sent.",
            }
        )

    if user.email_verified:
        return Response(
            {
                "success": True,
                "message": "Your email is already verified. You can sign in.",
            }
        )

    # Generate new token
    new_token = str(_uuid.uuid4())
    user.email_verification_token = new_token
    user.save(update_fields=["email_verification_token"])

    # Send verification email via Firebase (free) with Django fallback
    try:
        send_verification_email(user)
    except Exception:
        pass  # Email service may not be configured in dev

    return Response(
        {
            "success": True,
            "message": "Verification email sent. Please check your inbox.",
        }
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def google_auth(request):
    """
    POST /api/v1/auth/google/
    Body: { "access_token": "<google_access_token>" }

    Verifies Google access token, finds or creates a user, returns JWT tokens.
    """
    access_token = request.data.get("access_token")
    if not access_token:
        return Response(
            {"error": "Google access token is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Verify token with Google and get user info
    try:
        google_response = http_requests.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        if google_response.status_code != 200:
            return Response(
                {"error": "Invalid Google token."}, status=status.HTTP_400_BAD_REQUEST
            )
        google_data = google_response.json()
    except Exception:
        return Response(
            {"error": "Failed to verify Google token."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    google_id = google_data.get("sub")
    email = google_data.get("email")
    first_name = google_data.get("given_name", "")
    last_name = google_data.get("family_name", "")
    avatar_url = google_data.get("picture", "")
    email_verified_by_google = google_data.get("email_verified", False)

    if not email or not google_id:
        return Response(
            {"error": "Could not retrieve email from Google."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Find existing user by google_id or email
    user = None
    try:
        user = User.objects.get(google_id=google_id)
    except User.DoesNotExist:
        try:
            # Link existing email account
            user = User.objects.get(email=email)
            user.google_id = google_id
            if avatar_url and not user.avatar_url:
                user.avatar_url = avatar_url
            user.email_verified = user.email_verified or email_verified_by_google
            user.save(update_fields=["google_id", "avatar_url", "email_verified"])
        except User.DoesNotExist:
            # Create new user
            username_base = email.split("@")[0]
            username = username_base
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{username_base}{counter}"
                counter += 1

            user = User.objects.create_user(
                email=email,
                username=username,
                first_name=first_name,
                last_name=last_name,
                password=None,  # No password for Google users
                google_id=google_id,
                avatar_url=avatar_url,
                email_verified=email_verified_by_google,
            )
            user.set_unusable_password()
            user.save()

    # Return JWT tokens
    refresh = RefreshToken.for_user(user)
    return Response(
        {
            "success": True,
            "user": {
                "id": str(user.id),
                "email": user.email,
                "username": user.username,
                "first_name": user.first_name,
                "email_verified": user.email_verified,
                "avatar_url": user.avatar_url,
            },
            "tokens": {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
        }
    )


# ── Feature: User Activity Heatmap API ────────────────────────────────────────

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response as DRFResponse
from apps.core.models import UserActivity
from django.db.models.functions import TruncDate
from django.db.models import Count
from datetime import timedelta
from django.utils import timezone


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def user_activity_heatmap(request):
    """
    Return daily activity counts for the authenticated user.
    Query params: days (int, default 120), page_size (int, ignored - return all)
    Used by ActivityHeatmapCalendar component.
    """
    try:
        days = int(request.query_params.get("days", 120))
        days = min(max(days, 7), 365)
    except (ValueError, TypeError):
        days = 120

    since = timezone.now() - timedelta(days=days)

    qs = (
        UserActivity.objects
        .filter(user=request.user, timestamp__gte=since)
        .annotate(date=TruncDate("timestamp"))
        .values("date", "interaction_type")
        .annotate(count=Count("id"))
        .order_by("date")
    )

    # Aggregate by date
    by_date: dict = {}
    for row in qs:
        d = row["date"].isoformat()
        by_date[d] = by_date.get(d, 0) + row["count"]

    results = [{"date": d, "count": c} for d, c in sorted(by_date.items())]
    return DRFResponse({"success": True, "results": results, "days": days})
