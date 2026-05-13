"""
backend.apps.users.mfa
~~~~~~~~~~~~~~~~~~~~~~~~
TOTP-based Multi-Factor Authentication for admin accounts.

Phase 9.1 — Security Hardening

Uses django-otp + qrcode to implement:
  - TOTP device setup (secret generation + QR code)
  - TOTP verification
  - MFA enforcement for admin/staff users
  - Backup codes (10 single-use codes)

Dependencies:
  django-otp, qrcode[pil], cryptography (already in requirements)
"""

from __future__ import annotations

import hashlib
import io
import os
import secrets
import string
from typing import List, Optional

import structlog

logger = structlog.get_logger(__name__)

BACKUP_CODE_LENGTH = 10
BACKUP_CODE_COUNT = 10


# ── TOTP Device helpers ────────────────────────────────────────────────────────


def setup_totp_device(user) -> dict:
    """
    Create (or replace) a TOTP device for the user.
    Returns { secret, otpauth_url, qr_code_base64, backup_codes }
    """
    try:
        import base64

        import qrcode
        from django_otp.plugins.otp_totp.models import TOTPDevice

        # Remove existing devices
        TOTPDevice.objects.filter(user=user).delete()

        # Create new device (confirmed=False until first successful verify)
        device = TOTPDevice.objects.create(
            user=user,
            name=f"{user.email} — Authenticator",
            confirmed=False,
        )

        # Build otpauth:// URL
        issuer = "SYNAPSE"
        account = user.email
        otp_url = device.config_url

        # Generate QR code PNG → base64
        qr = qrcode.QRCode(box_size=6, border=2)
        qr.add_data(otp_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        qr_b64 = base64.b64encode(buffer.getvalue()).decode()

        # Generate backup codes
        backup_codes = _generate_backup_codes(user)

        logger.info("totp_device_created", user=user.email)
        return {
            "secret": device.bin_key.hex(),
            "otpauth_url": otp_url,
            "qr_code_base64": qr_b64,
            "backup_codes": backup_codes,
        }
    except ImportError as exc:
        logger.error("totp_setup_import_error", error=str(exc))
        raise RuntimeError(
            "MFA dependencies not installed. Run: pip install django-otp qrcode[pil]"
        ) from exc


def verify_totp_token(user, token: str) -> bool:
    """
    Verify a TOTP token (6-digit) for the user.
    Confirms the device on first successful verification.
    Returns True if valid, False otherwise.
    """
    try:
        from django_otp.plugins.otp_totp.models import TOTPDevice

        device = TOTPDevice.objects.filter(user=user).first()
        if not device:
            return False

        if device.verify_token(token):
            if not device.confirmed:
                device.confirmed = True
                device.save(update_fields=["confirmed"])
            logger.info("totp_verified", user=user.email)
            return True

        logger.warning("totp_invalid_token", user=user.email)
        return False
    except Exception as exc:
        logger.error("totp_verify_error", error=str(exc))
        return False


def user_has_mfa_enabled(user) -> bool:
    """Check if user has a confirmed TOTP device."""
    try:
        from django_otp.plugins.otp_totp.models import TOTPDevice

        return TOTPDevice.objects.filter(user=user, confirmed=True).exists()
    except Exception:
        return False


def disable_mfa(user) -> None:
    """Remove all TOTP devices and backup codes for the user."""
    try:
        from django_otp.plugins.otp_totp.models import TOTPDevice

        TOTPDevice.objects.filter(user=user).delete()
        # Clear stored backup codes
        user.preferences.pop("mfa_backup_codes", None)
        user.save(update_fields=["preferences"])
        logger.info("mfa_disabled", user=user.email)
    except Exception as exc:
        logger.error("mfa_disable_error", error=str(exc))


# ── Backup codes ───────────────────────────────────────────────────────────────


def _generate_backup_codes(user) -> List[str]:
    """
    Generate 10 single-use backup codes (format: XXXX-XXXX-XXXX).
    Codes are hashed before storage (SHA-256).
    Returns plain-text codes — shown once, then lost.
    """
    alphabet = string.ascii_uppercase + string.digits
    codes = []
    hashed = []

    for _ in range(BACKUP_CODE_COUNT):
        # 12 chars → 3 groups of 4
        raw = "".join(secrets.choice(alphabet) for _ in range(12))
        fmt = f"{raw[:4]}-{raw[4:8]}-{raw[8:]}"
        codes.append(fmt)
        hashed.append(hashlib.sha256(fmt.encode()).hexdigest())

    # Store hashed codes in user preferences
    user.preferences["mfa_backup_codes"] = hashed
    user.save(update_fields=["preferences"])
    return codes


def verify_backup_code(user, code: str) -> bool:
    """
    Verify and consume a backup code.
    Returns True if valid (and removes it from the list).
    """
    hashed_input = hashlib.sha256(code.upper().encode()).hexdigest()
    stored_hashes = user.preferences.get("mfa_backup_codes", [])

    if hashed_input in stored_hashes:
        stored_hashes.remove(hashed_input)
        user.preferences["mfa_backup_codes"] = stored_hashes
        user.save(update_fields=["preferences"])
        logger.info("backup_code_used", user=user.email, remaining=len(stored_hashes))
        return True

    logger.warning("backup_code_invalid", user=user.email)
    return False
