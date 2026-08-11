"""
SYNAPSE Google OAuth Views (server-side redirect flow)
Handles Google OAuth 2.0 login and callback.

Why this exists (in addition to the GSI id_token endpoint):
    The Google Identity Services (GSI) button loads
    https://accounts.google.com/gsi/client in the browser. On networks where
    that script is blocked or dropped (some ISPs/countries, ad-blockers), the
    button hangs on "Loading Google sign-in…" forever. The GitHub button has
    the same problem and was solved with a server-side redirect flow — this
    file gives Google the identical treatment:

    1. GET /api/v1/auth/google/redirect/   → 302 to Google's consent screen
    2. GET /api/v1/auth/google/callback/   → exchange code, create/link user,
                                              redirect to frontend with JWT

    No browser-side Google JS is involved, so it works on any network that
    can reach accounts.google.com for a plain page navigation.
"""

import logging
import os
import urllib.parse

import requests

from django.conf import settings
from django.shortcuts import redirect as django_redirect
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import User

logger = logging.getLogger(__name__)

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
FRONTEND_URL = getattr(settings, "FRONTEND_URL", "http://localhost:3000")

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


def _is_frontend_proxy_host(host: str) -> bool:
    """
    True when the request host is a frontend proxy rather than the backend.

    The Vercel frontend rewrites /api/v1/* to the Django backend, so requests
    that arrive through it carry X-Forwarded-Host = the Vercel origin (e.g.
    synapse-one-blond.vercel.app). Deriving the OAuth redirect URI from that
    host produces a callback URL the provider will reject with
    redirect_uri_mismatch. Skip it and fall through to the backend's own
    hostname (RENDER_EXTERNAL_HOSTNAME / env var) instead.
    """
    host = (host or "").strip().lower()
    if not host:
        return True
    if host.endswith(".vercel.app") or host.endswith(".vercel.com"):
        return True
    frontend_host = urllib.parse.urlparse(FRONTEND_URL).netloc.lower()
    return bool(frontend_host) and host == frontend_host


def _google_redirect_uri(request=None) -> str:
    """
    Production-safe Google callback URL — mirrors _github_redirect_uri.

    Priority:
      1. Explicit GOOGLE_REDIRECT_URI env var (matches what you registered in
         the Google Cloud console as an Authorized redirect URI).
      2. Derive from X-Forwarded-Host / Host headers — but SKIP frontend
         proxy hosts (Vercel rewrites /api/* → backend, so the forwarded host
         is the Vercel origin, not the backend).
      3. RENDER_EXTERNAL_HOSTNAME fallback.
    """
    env_uri = os.environ.get("GOOGLE_REDIRECT_URI", "").strip()
    if env_uri and "localhost" not in env_uri and "127.0.0.1" not in env_uri:
        return env_uri

    if request is not None:
        try:
            host = (
                request.META.get("HTTP_X_FORWARDED_HOST")
                or request.META.get("HTTP_HOST")
                or ""
            )
            scheme = request.META.get("HTTP_X_FORWARDED_PROTO", "https")
            if (
                host
                and "localhost" not in host
                and "127.0.0.1" not in host
                and not _is_frontend_proxy_host(host)
            ):
                return f"{scheme}://{host}/api/v1/auth/google/callback/"
        except Exception:
            pass

    render_host = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "").strip()
    if render_host:
        return f"https://{render_host}/api/v1/auth/google/callback/"

    return "http://localhost:8000/api/v1/auth/google/callback/"


def _get_tokens_for_user(user: User) -> dict:
    """Generate JWT access + refresh tokens for a user."""
    from rest_framework_simplejwt.tokens import RefreshToken

    refresh = RefreshToken.for_user(user)
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }


@api_view(["GET"])
@permission_classes([AllowAny])
def google_auth_redirect(request):
    """
    GET /api/v1/auth/google/redirect/
    Redirects the user to Google's OAuth consent screen.
    """
    if not GOOGLE_CLIENT_ID:
        return Response(
            {"error": "Google OAuth is not configured. Set GOOGLE_CLIENT_ID."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    params = urllib.parse.urlencode(
        {
            "client_id": GOOGLE_CLIENT_ID,
            "redirect_uri": _google_redirect_uri(request),
            "response_type": "code",
            "scope": "openid email profile",
            "access_type": "online",
            "state": "synapse_google_oauth",
        }
    )
    return django_redirect(f"{GOOGLE_AUTH_URL}?{params}")


@api_view(["GET"])
@permission_classes([AllowAny])
def google_callback(request):
    """
    GET /api/v1/auth/google/callback/
    Exchanges the OAuth code for tokens, fetches the Google profile, creates
    or links a SYNAPSE account, and redirects to the frontend with JWT tokens.
    """
    code = request.GET.get("code")
    error = request.GET.get("error")

    if error:
        logger.info("Google OAuth error param: %s", error)
        return django_redirect(f"{FRONTEND_URL}/login?error=google_denied")

    if not code:
        return Response(
            {"error": "Missing OAuth code parameter."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # ── Exchange code for Google tokens ────────────────────────────────────
    try:
        token_response = requests.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": _google_redirect_uri(request),
                "grant_type": "authorization_code",
            },
            timeout=10,
        )
        token_response.raise_for_status()
        token_data = token_response.json()
    except requests.RequestException as exc:
        logger.error("Google token exchange failed: %s", exc)
        return django_redirect(f"{FRONTEND_URL}/login?error=google_token_failed")

    access_token = token_data.get("access_token")
    if not access_token:
        logger.error("Google returned no access_token: %s", token_data)
        return django_redirect(f"{FRONTEND_URL}/login?error=google_no_token")

    # ── Fetch Google user profile ──────────────────────────────────────────
    try:
        profile_resp = requests.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        profile_resp.raise_for_status()
        google_data = profile_resp.json()
    except requests.RequestException as exc:
        logger.error("Google profile fetch failed: %s", exc)
        return django_redirect(f"{FRONTEND_URL}/login?error=google_profile_failed")

    google_id = google_data.get("sub")
    email = google_data.get("email")
    if not google_id or not email:
        logger.error("Google profile missing sub/email: %s", google_data)
        return django_redirect(f"{FRONTEND_URL}/login?error=google_no_email")

    first_name = google_data.get("given_name", "")
    last_name = google_data.get("family_name", "")
    avatar_url = google_data.get("picture", "")
    email_verified_by_google = google_data.get("email_verified", False)

    # ── Find or create SYNAPSE user ────────────────────────────────────────
    user = None
    try:
        user = User.objects.get(google_id=google_id)
    except User.DoesNotExist:
        try:
            # Link Google to an existing email account
            user = User.objects.get(email=email)
            user.google_id = google_id
            if avatar_url and not user.avatar_url:
                user.avatar_url = avatar_url
            user.email_verified = user.email_verified or email_verified_by_google
            user.save(update_fields=["google_id", "avatar_url", "email_verified"])
            logger.info("Linked Google to existing user %s", user.email)
        except User.DoesNotExist:
            # Create a new user
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
                password=None,
                google_id=google_id,
                avatar_url=avatar_url,
                email_verified=email_verified_by_google,
            )
            user.set_unusable_password()
            user.save()
            logger.info("Created new user via Google OAuth: %s", user.email)

    # ── Return JWT tokens via frontend redirect ───────────────────────────
    tokens = _get_tokens_for_user(user)
    redirect_url = (
        f"{FRONTEND_URL}/auth/google/success"
        f"?access={tokens['access']}"
        f"&refresh={tokens['refresh']}"
        f"&is_onboarded={str(user.is_onboarded).lower()}"
    )
    return django_redirect(redirect_url)
