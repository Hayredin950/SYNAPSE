"""
Text cleaning utilities for the SYNAPSE NLP pipeline.

Provides HTML stripping, Unicode normalization, and whitespace cleaning
so that downstream NLP models receive clean, consistent plain text.
"""

import logging
import re
import unicodedata

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def clean_html(html: str) -> str:
    """
    Strip HTML tags and return plain text.

    Uses BeautifulSoup to parse the markup and extract readable text.
    Falls back to the original string if parsing fails.

    Args:
        html: Raw HTML string (may also be plain text — safe to pass either).

    Returns:
        Plain-text string with all HTML tags removed.
    """
    if not html:
        return ""
    try:
        soup = BeautifulSoup(html, "html.parser")
        # Remove script / style blocks entirely
        for tag in soup(["script", "style", "noscript", "iframe"]):
            tag.decompose()
        text = soup.get_text(separator=" ")
        return text
    except Exception as exc:
        logger.warning("clean_html failed, returning raw input: %s", exc)
        return html


def normalize_whitespace(text: str) -> str:
    """
    Collapse multiple whitespace characters into a single space and strip edges.

    Args:
        text: Input string.

    Returns:
        Whitespace-normalised string.
    """
    text = re.sub(r"[ \t]+", " ", text)  # collapse horizontal whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)  # max two consecutive newlines
    return text.strip()


def normalize_unicode(text: str) -> str:
    """
    Apply NFKC Unicode normalisation and fix common encoding issues.

    NFKC decomposes compatibility characters and re-composes them in
    canonical form (e.g. ligatures → individual letters, full-width → ASCII).

    Args:
        text: Input string (may contain non-ASCII characters).

    Returns:
        NFKC-normalised string.
    """
    if not text:
        return ""
    return unicodedata.normalize("NFKC", text)


def remove_special_characters(text: str) -> str:
    """
    Remove non-printable control characters while keeping all printable Unicode.

    This preserves accented letters, CJK characters, punctuation, etc.,
    but strips invisible control codes (e.g. null bytes, bell, form-feed).

    Args:
        text: Input string.

    Returns:
        String with control characters removed.
    """
    # Keep printable chars only (category starting with C = control / other)
    return "".join(
        ch for ch in text if unicodedata.category(ch)[0] != "C" or ch in "\n\r\t"
    )


def clean_text(text: str, strip_html: bool = True) -> str:
    """
    Full text-cleaning pipeline: HTML strip → Unicode normalise →
    control-char removal → whitespace collapse.

    Args:
        text:       Raw input text (may contain HTML).
        strip_html: Whether to strip HTML tags first (default True).

    Returns:
        Clean, normalised plain-text string.
    """
    if not text:
        return ""

    if strip_html:
        text = clean_html(text)

    text = normalize_unicode(text)
    text = remove_special_characters(text)
    text = normalize_whitespace(text)
    return text
