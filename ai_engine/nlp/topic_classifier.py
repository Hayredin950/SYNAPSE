"""
Topic classification for the SYNAPSE NLP pipeline.

Uses **zero-shot classification** with ``facebook/bart-large-mnli`` so that
no labelled training data or model fine-tuning is required.  The model is
loaded once and cached for the lifetime of the process.

Predefined topics match the categories used across the platform (articles,
papers, repositories, videos).
"""

import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Canonical topic labels used throughout SYNAPSE
TECH_TOPICS: List[str] = [
    "Machine Learning",
    "Web Development",
    "DevOps",
    "Data Science",
    "Security",
    "Cloud Computing",
    "Mobile Development",
    "Game Development",
    "Blockchain",
    "Open Source",
    "Programming",
    "Artificial Intelligence",
    "Software Engineering",
    "Databases",
    "Networking",
]

# Model identifier — can be overridden via environment variable
DEFAULT_MODEL: str = "facebook/bart-large-mnli"

# Minimum score to accept the top label; below this threshold we return
# a generic "Technology" category.
MIN_CONFIDENCE: float = 0.20

# Module-level cache so the pipeline is only loaded once per process
_classifier = None


def _get_classifier():
    """Lazy-load and cache the zero-shot classification pipeline."""
    global _classifier
    if _classifier is None:
        try:
            import os

            from transformers import pipeline  # noqa: PLC0415

            model_name = os.environ.get("TOPIC_MODEL", DEFAULT_MODEL)
            logger.info("Loading zero-shot classifier: %s", model_name)
            _classifier = pipeline(
                "zero-shot-classification",
                model=model_name,
                device=-1,  # CPU; set to 0 for GPU
            )
            logger.info("Zero-shot classifier loaded successfully.")
        except Exception as exc:
            logger.error("Failed to load zero-shot classifier: %s", exc)
            _classifier = None
    return _classifier


def classify_topic(
    text: str,
    candidate_labels: Optional[List[str]] = None,
    min_confidence: float = MIN_CONFIDENCE,
) -> Tuple[str, float]:
    """
    Classify *text* into one of the predefined technology topics.

    Args:
        text:             Plain-text document to classify.
        candidate_labels: Override the default topic list (optional).
        min_confidence:   Minimum score to accept the top label.

    Returns:
        ``(topic_label, confidence_score)`` where score is in [0, 1].
        Falls back to ``("Technology", 0.0)`` on any failure.
    """
    if not text or len(text.split()) < 5:
        return ("Technology", 0.0)

    labels = candidate_labels or TECH_TOPICS
    classifier = _get_classifier()

    if classifier is None:
        logger.warning("Classifier unavailable; returning default topic.")
        return ("Technology", 0.0)

    try:
        # Truncate to keep inference fast (BART handles ~1 024 tokens)
        snippet = text[:2000]
        result: Dict = classifier(snippet, candidate_labels=labels, multi_label=False)
        top_label: str = result["labels"][0]
        top_score: float = round(result["scores"][0], 4)

        if top_score < min_confidence:
            return ("Technology", top_score)

        return (top_label, top_score)
    except Exception as exc:
        logger.error("Topic classification failed: %s", exc)
        return ("Technology", 0.0)


def classify_topic_scores(
    text: str,
    candidate_labels: Optional[List[str]] = None,
) -> List[Tuple[str, float]]:
    """
    Return scores for *all* candidate labels, sorted descending by score.

    Useful for multi-label tagging or analytics.

    Args:
        text:             Plain-text document.
        candidate_labels: Override the default topic list (optional).

    Returns:
        List of ``(topic, score)`` tuples, sorted highest-score first.
    """
    if not text or len(text.split()) < 5:
        return []

    labels = candidate_labels or TECH_TOPICS
    classifier = _get_classifier()
    if classifier is None:
        return []

    try:
        snippet = text[:2000]
        result: Dict = classifier(snippet, candidate_labels=labels, multi_label=True)
        return list(zip(result["labels"], [round(s, 4) for s in result["scores"]]))
    except Exception as exc:
        logger.error("Multi-label topic classification failed: %s", exc)
        return []
