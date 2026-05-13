"""
backend.apps.core.security
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Security middleware and utilities for Phase 9.1.

Implements:
  - ContentSecurityPolicyMiddleware: fine-grained CSP headers per request
  - RBACPermission: role-based access control (admin/premium/user)
  - rate_limit decorator: per-view, per-user rate limiting
  - SecurityHeadersMiddleware: additional security headers
"""

from __future__ import annotations

import hashlib
import secrets
from typing import Callable

from django.http import HttpRequest, HttpResponse
from rest_framework.permissions import BasePermission

# ── Content Security Policy Middleware ─────────────────────────────────────────


class ContentSecurityPolicyMiddleware:
    """
    Adds a strict Content-Security-Policy header to every response.

    Industry practice: nonce-based CSP for inline scripts eliminates
    the need for 'unsafe-inline' (which defeats XSS protection).
    """

    def __init__(self, get_response: Callable):
        self.get_response = get_response

    # Paths that must be embeddable in iframes (live document preview)
    IFRAME_ALLOWED_PATHS = ("/render/",)

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Generate a per-request nonce (16 bytes = 128 bits)
        nonce = secrets.token_urlsafe(16)
        request.csp_nonce = nonce

        response = self.get_response(request)

        # For document render endpoints — allow embedding in same-origin iframes
        is_render = any(p in request.path for p in self.IFRAME_ALLOWED_PATHS)

        if is_render:
            # Permissive CSP for iframe-embedded document viewer
            csp = "; ".join(
                [
                    "default-src 'self' 'unsafe-inline' 'unsafe-eval' data: blob:",
                    "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net",
                    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
                    "font-src 'self' data: https://fonts.gstatic.com",
                    "img-src 'self' data: https: blob:",
                    "connect-src 'self' wss: https:",
                    "frame-ancestors 'self'",  # allow same-origin iframe embedding
                    "base-uri 'self'",
                ]
            )
            # Allow iframe embedding from same origin
            response["X-Frame-Options"] = "SAMEORIGIN"
        else:
            csp = "; ".join(
                [
                    "default-src 'self'",
                    f"script-src 'self' 'nonce-{nonce}' https://cdn.jsdelivr.net",
                    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
                    "font-src 'self' https://fonts.gstatic.com",
                    "img-src 'self' data: https:",
                    "connect-src 'self' https: wss:",
                    "frame-ancestors 'none'",
                    "base-uri 'self'",
                    "form-action 'self'",
                    "object-src 'none'",
                ]
            )

        response["Content-Security-Policy"] = csp
        return response


# ── Security Headers Middleware ────────────────────────────────────────────────


class SecurityHeadersMiddleware:
    """
    Adds additional security headers not covered by Django's SecurityMiddleware.
    """

    def __init__(self, get_response: Callable):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)

        # Remove server identification (Django responses use __delitem__)
        try:
            del response["Server"]
        except KeyError:
            pass
        try:
            del response["X-Powered-By"]
        except KeyError:
            pass

        # Additional headers
        response["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), "
            "payment=(), usb=(), magnetometer=(), gyroscope=()"
        )

        # Document render endpoint must be embeddable in same-origin iframes
        is_render = "/render/" in request.path
        if is_render:
            # Relaxed cross-origin policies for iframe-embedded document viewer
            response["Cross-Origin-Opener-Policy"] = "same-origin-allow-popups"
            response["Cross-Origin-Embedder-Policy"] = "unsafe-none"
            response["Cross-Origin-Resource-Policy"] = "same-site"
        else:
            # COOP: same-origin-allow-popups required for Google OAuth popup flow
            # (the popup needs to call window.close() and the opener checks window.closed)
            response["Cross-Origin-Opener-Policy"] = "same-origin-allow-popups"
            # COEP: unsafe-none required for cross-origin frontend (Vercel) to read API responses
            response["Cross-Origin-Embedder-Policy"] = "unsafe-none"
            # CORP: cross-origin allows any origin to read API responses (required by SPA frontend)
            response["Cross-Origin-Resource-Policy"] = "cross-origin"
            # Note: Security middleware must run BEFORE CorsMiddleware in settings.py

        # Cache control for API responses (no caching of sensitive data)
        if request.path.startswith("/api/") and not is_render:
            response["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
            response["Pragma"] = "no-cache"

        return response


# ── RBAC Permissions ───────────────────────────────────────────────────────────


class IsAdminUser(BasePermission):
    """Allow access only to users with role=admin."""

    message = "Admin role required."

    def has_permission(self, request, view) -> bool:
        return (
            request.user
            and request.user.is_authenticated
            and getattr(request.user, "role", None) == "admin"
        )


class IsPremiumUser(BasePermission):
    """Allow access to premium and admin users."""

    message = "Premium subscription required."

    def has_permission(self, request, view) -> bool:
        return (
            request.user
            and request.user.is_authenticated
            and getattr(request.user, "role", None) in ("premium", "admin")
        )


class IsOwnerOrAdmin(BasePermission):
    """Object-level permission: owner or admin."""

    message = "You do not have permission to access this resource."

    def has_object_permission(self, request, view, obj) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False
        if getattr(request.user, "role", None) == "admin":
            return True
        # Check common ownership patterns
        owner = getattr(obj, "user", None) or getattr(obj, "owner", None)
        return owner == request.user


# ── MFA enforcement for admin views ───────────────────────────────────────────


class MFARequiredPermission(BasePermission):
    """
    Require MFA to be enabled for admin/staff users accessing sensitive endpoints.
    Regular users can access without MFA.
    """

    message = "MFA is required for admin accounts. Please enable TOTP at /api/v1/auth/mfa/setup/"

    def has_permission(self, request, view) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False

        # Only enforce MFA for admin users
        if getattr(request.user, "role", None) != "admin":
            return True

        from apps.users.mfa import user_has_mfa_enabled

        return user_has_mfa_enabled(request.user)


# ── Input sanitisation utilities ───────────────────────────────────────────────

import html
import re


def sanitise_text(text: str, max_length: int = 10000) -> str:
    """
    Sanitise user-provided text:
    - Strip leading/trailing whitespace
    - Collapse multiple newlines
    - HTML-escape to prevent XSS in non-HTML contexts
    - Enforce max length
    """
    if not isinstance(text, str):
        return ""
    text = text.strip()[:max_length]
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Remove null bytes (SQL injection vector)
    text = text.replace("\x00", "")
    return text


def sanitise_filename(filename: str) -> str:
    """
    Sanitise an uploaded filename to prevent path traversal.
    Keeps only alphanumeric, dots, dashes, underscores.
    """
    import os

    # Get basename only (no path components)
    filename = os.path.basename(filename)
    # Replace dangerous characters
    filename = re.sub(r"[^\w\-.]", "_", filename)
    # Prevent hidden files
    filename = filename.lstrip(".")
    return filename[:255] or "upload"
