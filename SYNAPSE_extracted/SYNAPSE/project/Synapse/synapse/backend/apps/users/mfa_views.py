"""
backend.apps.users.mfa_views
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
REST API views for TOTP MFA management.

Phase 9.1 — Security Hardening

Endpoints (mounted at /api/v1/auth/mfa/):
  GET  /setup/           → generate TOTP secret + QR code
  POST /setup/confirm/   → confirm TOTP device with first token
  POST /verify/          → verify TOTP during login (2nd factor)
  POST /verify-backup/   → verify backup code
  POST /disable/         → disable MFA (requires password)
  GET  /status/          → MFA enabled status
"""

from __future__ import annotations

from rest_framework_simplejwt.tokens import RefreshToken

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle


class MFAVerifyThrottle(UserRateThrottle):
    """Strict rate limit for MFA endpoints — max 5 attempts per minute per user."""

    rate = "5/minute"
    scope = "mfa_verify"


class MFASetupThrottle(UserRateThrottle):
    """Rate limit for MFA setup — max 3 per minute."""

    rate = "3/minute"
    scope = "mfa_setup"


from .mfa import (
    disable_mfa,
    setup_totp_device,
    user_has_mfa_enabled,
    verify_backup_code,
    verify_totp_token,
)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@throttle_classes([MFASetupThrottle])
def mfa_setup(request: Request) -> Response:
    """Generate TOTP secret + QR code for the authenticated user."""
    try:
        data = setup_totp_device(request.user)
        return Response(
            {
                "success": True,
                "qr_code": f"data:image/png;base64,{data['qr_code_base64']}",
                "otpauth_url": data["otpauth_url"],
                "backup_codes": data["backup_codes"],
                "message": "Scan the QR code with your authenticator app, then confirm with /mfa/setup/confirm/",
            }
        )
    except RuntimeError as exc:
        return Response(
            {"success": False, "error": str(exc)},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    except Exception as exc:
        return Response(
            {"success": False, "error": "MFA setup failed."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def mfa_setup_confirm(request: Request) -> Response:
    """Confirm TOTP device with first 6-digit token."""
    token = request.data.get("token", "").strip()
    if not token or len(token) != 6 or not token.isdigit():
        return Response(
            {"success": False, "error": "token must be a 6-digit number."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if verify_totp_token(request.user, token):
        return Response(
            {
                "success": True,
                "message": "MFA enabled successfully. Keep your backup codes safe!",
            }
        )
    return Response(
        {"success": False, "error": "Invalid token. Please try again."},
        status=status.HTTP_400_BAD_REQUEST,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([MFAVerifyThrottle])
def mfa_verify(request: Request) -> Response:
    """
    Verify TOTP token as 2nd factor during login.
    On success returns fresh JWT tokens.
    """
    token = request.data.get("token", "").strip()
    if not token:
        return Response(
            {"success": False, "error": "token is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if verify_totp_token(request.user, token):
        refresh = RefreshToken.for_user(request.user)
        return Response(
            {
                "success": True,
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            }
        )

    return Response(
        {"success": False, "error": "Invalid or expired token."},
        status=status.HTTP_401_UNAUTHORIZED,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([MFAVerifyThrottle])
def mfa_verify_backup(request: Request) -> Response:
    """Verify a backup code (single-use)."""
    code = request.data.get("code", "").strip()
    if not code:
        return Response(
            {"success": False, "error": "code is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if verify_backup_code(request.user, code):
        refresh = RefreshToken.for_user(request.user)
        return Response(
            {
                "success": True,
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "message": "Backup code accepted. Consider re-generating backup codes.",
            }
        )

    return Response(
        {"success": False, "error": "Invalid or already used backup code."},
        status=status.HTTP_401_UNAUTHORIZED,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([MFAVerifyThrottle])
def mfa_disable(request: Request) -> Response:
    """Disable MFA (requires current password for confirmation)."""
    password = request.data.get("password", "")
    if not request.user.check_password(password):
        return Response(
            {"success": False, "error": "Incorrect password."},
            status=status.HTTP_403_FORBIDDEN,
        )

    disable_mfa(request.user)
    return Response({"success": True, "message": "MFA disabled."})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def mfa_status(request: Request) -> Response:
    """Return MFA enabled status for the current user."""
    enabled = user_has_mfa_enabled(request.user)
    return Response(
        {
            "mfa_enabled": enabled,
            "backup_codes_remaining": len(
                request.user.preferences.get("mfa_backup_codes", [])
            ),
        }
    )
