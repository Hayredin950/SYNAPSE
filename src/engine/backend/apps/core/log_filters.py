"""
PII Redaction Logging Filter

Redacts sensitive information from logs:
- Email addresses: user@domain.com → u***@***.com
- Credit card numbers (16 digits): → [REDACTED-CC]
- API keys (sk-syn-*): → sk-syn-[REDACTED]
- JWT tokens (eyJ...): → [REDACTED-JWT]

Usage:
    Add to LOGGING['filters'] in settings:
        'pii_redaction': {
            '()': 'apps.core.log_filters.PiiRedactionFilter',
        }

    Add to handler definitions:
        'filters': ['pii_redaction'],
"""

import logging
import re
from typing import Optional


class PiiRedactionFilter(logging.Filter):
    """Redacts Personally Identifiable Information from log records."""

    # Email pattern: user@domain.com → u***@***.com
    EMAIL_PATTERN = re.compile(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", re.IGNORECASE
    )

    # Credit card pattern: 16 consecutive digits → [REDACTED-CC]
    CREDIT_CARD_PATTERN = re.compile(
        r"\b(?:\d[ -]*?){13}(?:\d[ -]*?){3}\b|\b\d{16}\b", re.IGNORECASE
    )

    # API key pattern: sk-syn-* → sk-syn-[REDACTED]
    API_KEY_PATTERN = re.compile(r"(sk-syn-)[A-Za-z0-9_-]+", re.IGNORECASE)

    # JWT token pattern: eyJ... (base64-like) → [REDACTED-JWT]
    JWT_PATTERN = re.compile(
        r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b", re.IGNORECASE
    )

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Filter a log record to redact PII.

        Args:
            record: The LogRecord to filter

        Returns:
            True to allow the record through (always)
        """
        if record.msg:
            record.msg = self._redact_pii(str(record.msg))

        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: self._redact_pii(str(v)) for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(self._redact_pii(str(arg)) for arg in record.args)

        return True

    @classmethod
    def _redact_pii(cls, text: str) -> str:
        """
        Redact all PII patterns from text.

        Args:
            text: The text to redact

        Returns:
            Text with PII patterns redacted
        """
        if not text:
            return text

        # Redact emails: user@domain.com → u***@***.com
        text = cls.EMAIL_PATTERN.sub(lambda m: cls._redact_email(m.group(0)), text)

        # Redact credit cards: 1234567890123456 → [REDACTED-CC]
        text = cls.CREDIT_CARD_PATTERN.sub("[REDACTED-CC]", text)

        # Redact API keys: sk-syn-abc123xyz → sk-syn-[REDACTED]
        text = cls.API_KEY_PATTERN.sub(r"\1[REDACTED]", text)

        # Redact JWT tokens: eyJ... → [REDACTED-JWT]
        text = cls.JWT_PATTERN.sub("[REDACTED-JWT]", text)

        return text

    @staticmethod
    def _redact_email(email: str) -> str:
        """
        Redact an email address to first char + *** @ *** + TLD.

        Example:
            user@example.com → u***@***.com

        Args:
            email: The email to redact

        Returns:
            Redacted email
        """
        if "@" not in email:
            return email

        local, domain = email.split("@", 1)

        if not local:
            return email

        # Keep first character of local part
        redacted_local = local[0] + "***"

        # Keep only TLD (e.g., .com, .co.uk)
        domain_parts = domain.split(".")
        if len(domain_parts) >= 2:
            redacted_domain = "***." + domain_parts[-1]
        else:
            redacted_domain = "***"

        return f"{redacted_local}@{redacted_domain}"
