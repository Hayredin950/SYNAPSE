"""
Sentiment analysis for the SYNAPSE NLP pipeline.

Uses ``cardiffnlp/twitter-roberta-base-sentiment`` (as specified in TASKS.md)
to classify text as POSITIVE, NEGATIVE, or NEUTRAL with a confidence score.

The pipeline is loaded lazily and cached for the lifetime of the process.
Texts longer than 512 tokens are split into chunks and the final sentiment
is determined by the highest-confidence prediction across chunks.
"""

import logging
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# HuggingFace model identifier
DEFAULT_MODEL: str = "cardiffnlp/twitter-roberta-base-sentiment"

# Max characters to feed per chunk (≈ 512 tokens @ ~4 chars/token)
MAX_CHARS_PER_CHUNK: int = 1800

# Label mapping from model-specific labels to normalised labels
LABEL_MAP: Dict[str, str] = {
    "LABEL_0": "NEGATIVE",
    "LABEL_1": "NEUTRAL",
    "LABEL_2": "POSITIVE",
    # Some model variants use descriptive names directly
    "negative": "NEGATIVE",
    "neutral": "NEUTRAL",
    "positive": "POSITIVE",
}

# Module-level cache
_sentiment_pipeline = None


def _get_pipeline():
    """Lazy-load and cache the sentiment analysis pipeline."""
    global _sentiment_pipeline
    if _sentiment_pipeline is None:
        try:
            import os

            from transformers import pipeline  # noqa: PLC0415

            model_name = os.environ.get("SENTIMENT_MODEL", DEFAULT_MODEL)
            logger.info("Loading sentiment pipeline: %s", model_name)
            _sentiment_pipeline = pipeline(
                "sentiment-analysis",
                model=model_name,
                tokenizer=model_name,
                device=-1,  # CPU; set to 0 for GPU
                truncation=True,
                max_length=512,
            )
            logger.info("Sentiment pipeline loaded successfully.")
        except Exception as exc:
            logger.error("Failed to load sentiment pipeline: %s", exc)
            _sentiment_pipeline = None
    return _sentiment_pipeline


def _chunk_text(text: str, chunk_size: int = MAX_CHARS_PER_CHUNK) -> list:
    """
    Split *text* into overlapping chunks of at most *chunk_size* characters.

    Each chunk ends at a sentence boundary ('. ', '! ', '? ') when possible.
    """
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        if end < len(text):
            # Try to break at sentence boundary
            for sep in (". ", "! ", "? ", "\n"):
                boundary = text.rfind(sep, start, end)
                if boundary != -1:
                    end = boundary + len(sep)
                    break
        chunks.append(text[start:end].strip())
        start = end
    return [c for c in chunks if c]


def analyze_sentiment(text: str) -> Tuple[str, float]:
    """
    Analyse the sentiment of *text*.

    Long texts are split into chunks; the chunk with the highest confidence
    score determines the final result.

    Args:
        text: Plain text to analyse.

    Returns:
        ``(sentiment_label, score)`` where label is one of
        ``"POSITIVE"``, ``"NEGATIVE"``, ``"NEUTRAL"`` and score ∈ [0, 1].
        Returns ``("NEUTRAL", 0.0)`` on failure.
    """
    if not text or len(text.split()) < 3:
        return ("NEUTRAL", 0.0)

    pipe = _get_pipeline()
    if pipe is None:
        logger.warning("Sentiment pipeline unavailable; returning NEUTRAL.")
        return ("NEUTRAL", 0.0)

    try:
        chunks = _chunk_text(text)
        best_label = "NEUTRAL"
        best_score = 0.0

        for chunk in chunks:
            results = pipe(chunk)
            if not results:
                continue
            result = results[0]
            raw_label: str = result["label"]
            score: float = round(result["score"], 4)
            label = LABEL_MAP.get(raw_label, raw_label.upper())

            if score > best_score:
                best_score = score
                best_label = label

        return (best_label, best_score)

    except Exception as exc:
        logger.error("Sentiment analysis failed: %s", exc)
        return ("NEUTRAL", 0.0)


def sentiment_to_score(label: str, confidence: float) -> Optional[float]:
    """
    Convert a ``(label, confidence)`` pair into a signed float in [-1, 1].

    Convention:
    - POSITIVE → +confidence
    - NEGATIVE → -confidence
    - NEUTRAL  → 0.0

    This scalar is stored in ``Article.sentiment_score``.

    Args:
        label:      Sentiment label string.
        confidence: Model confidence in [0, 1].

    Returns:
        Signed float in [-1, 1].
    """
    label = label.upper()
    if label == "POSITIVE":
        return round(confidence, 4)
    if label == "NEGATIVE":
        return round(-confidence, 4)
    return 0.0
