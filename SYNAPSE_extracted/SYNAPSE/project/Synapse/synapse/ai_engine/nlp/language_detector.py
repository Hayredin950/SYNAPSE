"""
Language detection for the SYNAPSE NLP pipeline.

Uses the ``langdetect`` library to identify the language of a piece of
text. Articles that are not English are flagged so the pipeline can skip
expensive NLP operations on them.
"""

import logging
from typing import Tuple

logger = logging.getLogger(__name__)

# Minimum confidence threshold to accept a language detection result.
# langdetect returns a probability in [0, 1].
MIN_CONFIDENCE: float = 0.80


def detect_language(text: str) -> Tuple[str, float]:
    """
    Detect the language of *text*.

    Args:
        text: Plain text to analyse (should be at least a few words long).

    Returns:
        A ``(language_code, confidence)`` tuple, e.g. ``("en", 0.99)``.
        Returns ``("unknown", 0.0)`` when detection fails.
    """
    if not text or len(text.split()) < 5:
        # Too short to detect reliably — assume English to avoid false negatives
        return ("en", 1.0)

    try:
        from langdetect import detect_langs  # lazy import — not always installed

        results = detect_langs(text[:2000])  # limit to first 2 000 chars for speed
        if results:
            top = results[0]
            return (top.lang, round(top.prob, 4))
        return ("unknown", 0.0)
    except Exception as exc:
        logger.warning("Language detection failed: %s", exc)
        return ("unknown", 0.0)


def is_english(text: str, min_confidence: float = MIN_CONFIDENCE) -> bool:
    """
    Return ``True`` when *text* is English with at least *min_confidence*.

    Args:
        text:           Plain text to evaluate.
        min_confidence: Minimum probability threshold (0–1).

    Returns:
        ``True`` if English, ``False`` otherwise.
    """
    lang, confidence = detect_language(text)
    return lang == "en" and confidence >= min_confidence
