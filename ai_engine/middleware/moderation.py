"""
ai_engine.middleware.moderation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
OpenAI Moderation API integration — screens every user input before sending
to the LLM to detect and block harmful content.

TASK-004-B4

Usage:
    from ai_engine.middleware.moderation import check_moderation

    check_moderation(text, user_id="user-123")  # raises ModerationFlaggedError if harmful
"""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Import openai at module level so it can be patched in tests.
# Guarded with try/except so the module loads even when the package isn't installed.
try:
    import openai as _openai_module
except ImportError:  # pragma: no cover
    _openai_module = None  # type: ignore[assignment]

# ── Config ─────────────────────────────────────────────────────────────────────
# Read at call time (not module level) so that environment variable overrides
# (e.g. in tests using patch.dict) take effect correctly.


def _is_moderation_enabled() -> bool:
    return os.environ.get("MODERATION_ENABLED", "true").lower() == "true"


def _get_openai_api_key() -> str:
    return os.environ.get("OPENAI_API_KEY", "")


# Categories we treat as hard-block (refuse + log)
HARD_BLOCK_CATEGORIES = {
    "sexual/minors",
    "violence/graphic",
    "self-harm/instructions",
    "harassment/threatening",
}

# Categories we soft-block (warn but allow through with extra caution flag)
SOFT_BLOCK_CATEGORIES = {
    "sexual",
    "violence",
    "self-harm",
    "harassment",
    "hate",
    "hate/threatening",
    "self-harm/intent",
}


class ModerationFlaggedError(Exception):
    """Raised when content is flagged by OpenAI Moderation API."""

    def __init__(
        self,
        categories: dict,
        scores: dict,
        hard_block: bool = False,
        user_id: Optional[str] = None,
    ):
        self.categories = categories
        self.scores = scores
        self.hard_block = hard_block
        self.user_id = user_id
        flagged_cats = [k for k, v in categories.items() if v]
        super().__init__(f"Content flagged by moderation: {', '.join(flagged_cats)}")


def check_moderation(text: str, user_id: Optional[str] = None) -> dict:
    """
    Screen input text using the OpenAI Moderation API.

    Args:
        text:    The user input to screen.
        user_id: Optional user identifier for logging.

    Returns:
        dict with keys: flagged (bool), categories (dict), scores (dict), hard_block (bool)

    Raises:
        ModerationFlaggedError: If content is flagged (hard-block categories always raise;
                                 soft-block categories also raise).
    """
    if not _is_moderation_enabled() or not text or not text.strip():
        return {"flagged": False, "categories": {}, "scores": {}, "hard_block": False}

    openai_api_key = _get_openai_api_key()
    if not openai_api_key:
        logger.debug("moderation_skipped: OPENAI_API_KEY not set")
        return {"flagged": False, "categories": {}, "scores": {}, "hard_block": False}

    if _openai_module is None:  # pragma: no cover
        logger.warning("moderation_skipped: openai package not installed")
        return {"flagged": False, "categories": {}, "scores": {}, "hard_block": False}

    try:
        client = _openai_module.OpenAI(api_key=openai_api_key)
        response = client.moderations.create(
            input=text[:4096],  # Moderation API limit
            model="omni-moderation-latest",
        )
        result = response.results[0]

        categories: dict = dict(result.categories)
        scores: dict = dict(result.category_scores)
        flagged: bool = result.flagged

        if not flagged:
            return {
                "flagged": False,
                "categories": categories,
                "scores": scores,
                "hard_block": False,
            }

        # Determine if any hard-block category is flagged
        hard_block = any(categories.get(cat, False) for cat in HARD_BLOCK_CATEGORIES)

        flagged_cats = [k for k, v in categories.items() if v]
        logger.warning(
            "moderation_flagged user=%s categories=%s hard_block=%s input_excerpt='%.80s'",
            user_id,
            flagged_cats,
            hard_block,
            text,
        )

        raise ModerationFlaggedError(
            categories=categories,
            scores=scores,
            hard_block=hard_block,
            user_id=user_id,
        )

    except ModerationFlaggedError:
        raise
    except Exception as exc:
        # ERR-07: Moderation API failure — fail CLOSED (block) rather than
        # allowing content through. Silently allowing through on network error
        # creates a moderation bypass vector: an attacker could trigger API
        # failures to circumvent content filtering.
        #
        # We raise ModerationFlaggedError with hard_block=False so callers
        # can distinguish "definitely harmful" from "cannot verify" and apply
        # appropriate UX (e.g. "Service temporarily unavailable" vs "Blocked").
        logger.error(
            "moderation_api_error user=%s error=%s — blocking request (fail-closed)",
            user_id,
            exc,
        )
        raise ModerationFlaggedError(
            categories={"service_unavailable": True},
            scores={},
            hard_block=False,
            user_id=user_id,
        ) from exc
