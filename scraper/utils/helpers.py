"""
Utility helper functions for the SYNAPSE scraper.

Provides common utilities for URL deduplication, HTML cleaning,
text processing, datetime parsing, and safe type conversions.
"""

import hashlib
import re
from datetime import datetime
from typing import Optional
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from bs4 import BeautifulSoup


def sha256_hash(text: str) -> str:
    """
    Return SHA-256 hex digest of a string.

    Used for URL deduplication and content fingerprinting.

    Args:
        text: String to hash

    Returns:
        SHA-256 hex digest (64 characters)
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def clean_html(html: str) -> str:
    """
    Strip HTML tags and return plain text.

    Uses BeautifulSoup to parse and extract text from HTML,
    preserving line breaks where appropriate.

    Args:
        html: HTML string to clean

    Returns:
        Plain text content with minimal whitespace
    """
    if not html:
        return ""

    try:
        soup = BeautifulSoup(html, "html.parser")

        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()

        # Get text
        text = soup.get_text(separator=" ", strip=True)

        # Clean up excessive whitespace
        text = re.sub(r"\s+", " ", text)
        text = text.strip()

        return text
    except Exception:
        # Fallback: basic regex strip if BeautifulSoup fails
        text = re.sub(r"<[^>]+>", "", html)
        text = re.sub(r"\s+", " ", text)
        return text.strip()


def truncate(text: str, max_len: int, suffix: str = "...") -> str:
    """
    Truncate text to max_len characters, appending suffix if truncated.

    Args:
        text: Text to truncate
        max_len: Maximum length (including suffix)
        suffix: String to append if truncated (default: '...')

    Returns:
        Truncated text with suffix if needed
    """
    if not text:
        return text

    if len(text) <= max_len:
        return text

    # Account for suffix length when truncating
    truncate_at = max_len - len(suffix)
    if truncate_at < 0:
        truncate_at = 0

    return text[:truncate_at] + suffix


def parse_iso_datetime(date_str: str) -> Optional[datetime]:
    """
    Parse ISO 8601 datetime string to a timezone-aware datetime.

    Handles various ISO 8601 formats including:
    - 2024-01-15T10:30:00Z
    - 2024-01-15T10:30:00+00:00
    - 2024-01-15T10:30:00.123456Z
    - 2024-01-15 10:30:00

    Args:
        date_str: ISO 8601 formatted datetime string

    Returns:
        Timezone-aware datetime object, or None if parsing fails
    """
    if not date_str:
        return None

    date_str = date_str.strip()

    # Handle common ISO 8601 formats
    formats = [
        "%Y-%m-%dT%H:%M:%S.%fZ",  # 2024-01-15T10:30:00.123456Z
        "%Y-%m-%dT%H:%M:%SZ",  # 2024-01-15T10:30:00Z
        "%Y-%m-%dT%H:%M:%S.%f%z",  # 2024-01-15T10:30:00.123456+00:00
        "%Y-%m-%dT%H:%M:%S%z",  # 2024-01-15T10:30:00+00:00
        "%Y-%m-%dT%H:%M:%S",  # 2024-01-15T10:30:00
        "%Y-%m-%d %H:%M:%S",  # 2024-01-15 10:30:00
        "%Y-%m-%d",  # 2024-01-15
    ]

    # Handle +00:00 format by converting to Z
    if "+" in date_str or (date_str.count("-") > 2):
        # Try parsing with timezone
        for fmt in formats:
            if "%z" in fmt:
                try:
                    # Remove colon from timezone offset for strptime
                    if date_str[-6] in "+-" and date_str[-3] == ":":
                        date_str_clean = date_str[:-3] + date_str[-2:]
                    else:
                        date_str_clean = date_str

                    return datetime.strptime(date_str_clean, fmt)
                except ValueError:
                    continue

    # Try parsing without timezone
    for fmt in formats:
        if "%z" not in fmt:
            try:
                dt = datetime.strptime(date_str, fmt)
                # Make it timezone-aware (UTC)
                if dt.tzinfo is None:
                    from datetime import timezone

                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                continue

    return None


def normalize_url(url: str) -> str:
    """
    Normalize URL by lowercasing scheme and host, removing trailing slash,
    and stripping common tracking parameters.

    Removed parameters:
    - utm_source, utm_medium, utm_campaign, utm_term, utm_content
    - ref, fbclid

    Args:
        url: URL to normalize

    Returns:
        Normalized URL string
    """
    if not url:
        return url

    try:
        parsed = urlparse(url)

        # Lowercase scheme and netloc
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()
        path = parsed.path.rstrip("/")

        # Parse query parameters
        query_params = parse_qs(parsed.query, keep_blank_values=True)

        # Remove tracking parameters
        tracking_params = {
            "utm_source",
            "utm_medium",
            "utm_campaign",
            "utm_term",
            "utm_content",
            "ref",
            "fbclid",
        }

        # Filter out tracking parameters
        filtered_params = {
            k: v for k, v in query_params.items() if k.lower() not in tracking_params
        }

        # Reconstruct query string
        new_query = urlencode(filtered_params, doseq=True)

        # Reconstruct URL
        normalized = urlunparse((scheme, netloc, path, parsed.params, new_query, ""))

        return normalized
    except Exception:
        # Return original URL if normalization fails
        return url


def safe_int(value, default: int = 0) -> int:
    """
    Safely convert value to int, returning default on failure.

    Handles various input types including strings with whitespace,
    floats, and invalid inputs.

    Args:
        value: Value to convert to int
        default: Default value if conversion fails (default: 0)

    Returns:
        Converted integer or default value
    """
    if value is None:
        return default

    try:
        # Try direct conversion
        return int(value)
    except (ValueError, TypeError):
        pass

    try:
        # Try converting string by stripping whitespace
        if isinstance(value, str):
            return int(value.strip())
    except (ValueError, TypeError):
        pass

    try:
        # Try converting float to int
        if isinstance(value, float):
            return int(value)
    except (ValueError, TypeError):
        pass

    return default
