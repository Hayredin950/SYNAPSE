"""
Article summarization for the SYNAPSE NLP pipeline.

Uses Facebook's ``facebook/bart-large-cnn`` model (abstractive summarisation)
to generate concise summaries of articles.  The model is loaded lazily and
cached for the lifetime of the process.

Long articles are split into chunks, each chunk is summarised, and the
partial summaries are combined into a final summary.
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# HuggingFace model — can be overridden via environment variable
DEFAULT_MODEL: str = "facebook/bart-large-cnn"

# Summary generation parameters (as per documentation)
MAX_LENGTH: int = 150
MIN_LENGTH: int = 50

# Minimum number of words for the text to be worth summarising
MIN_WORDS: int = 50

# Maximum characters per chunk when splitting long articles
# BART handles ~1 024 tokens ≈ 4 000 chars safely
MAX_CHARS_PER_CHUNK: int = 3500

# Module-level cache
_summarizer = None


def _get_summarizer():
    """Lazy-load and cache the summarization pipeline."""
    global _summarizer
    if _summarizer is None:
        try:
            from transformers import pipeline  # noqa: PLC0415

            model_name = os.environ.get("SUMMARIZER_MODEL", DEFAULT_MODEL)
            logger.info("Loading summarizer: %s", model_name)
            _summarizer = pipeline(
                "summarization",
                model=model_name,
                device=-1,  # CPU; set to 0 for GPU
                truncation=True,
            )
            logger.info("Summarizer loaded successfully.")
        except Exception as exc:
            logger.error("Failed to load summarizer: %s", exc)
            _summarizer = None
    return _summarizer


def _split_into_chunks(text: str, max_chars: int = MAX_CHARS_PER_CHUNK) -> list:
    """
    Split *text* into chunks of at most *max_chars* characters.

    Attempts to break at paragraph or sentence boundaries.
    """
    if len(text) <= max_chars:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + max_chars
        if end < len(text):
            for sep in ("\n\n", "\n", ". ", "! ", "? "):
                boundary = text.rfind(sep, start, end)
                if boundary != -1:
                    end = boundary + len(sep)
                    break
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end
    return chunks


def summarize(
    text: str,
    max_length: int = MAX_LENGTH,
    min_length: int = MIN_LENGTH,
) -> Optional[str]:
    """
    Generate an abstractive summary of *text*.

    For texts shorter than ``MIN_WORDS`` words, returns the original text.
    For long texts, chunks are summarised individually and combined.

    Args:
        text:       Plain-text article content.
        max_length: Maximum token length of the generated summary.
        min_length: Minimum token length of the generated summary.

    Returns:
        Summary string, or the original text if it is too short,
        or ``None`` if the model is unavailable.
    """
    if not text:
        return None

    word_count = len(text.split())
    if word_count < MIN_WORDS:
        logger.debug(
            "Text too short to summarise (%d words); returning as-is.", word_count
        )
        return text.strip()

    pipe = _get_summarizer()
    if pipe is None:
        logger.warning("Summarizer unavailable.")
        return None

    try:
        chunks = _split_into_chunks(text)

        if len(chunks) == 1:
            result = pipe(
                chunks[0],
                max_length=max_length,
                min_length=min_length,
                do_sample=False,
            )
            return result[0]["summary_text"].strip()

        # Summarise each chunk then combine and re-summarise
        partial_summaries = []
        for chunk in chunks:
            result = pipe(
                chunk,
                max_length=max_length,
                min_length=min(min_length, 30),
                do_sample=False,
            )
            partial_summaries.append(result[0]["summary_text"].strip())

        combined = " ".join(partial_summaries)

        # Final pass to condense the partial summaries
        if len(combined.split()) > min_length:
            final = pipe(
                combined[:MAX_CHARS_PER_CHUNK],
                max_length=max_length,
                min_length=min_length,
                do_sample=False,
            )
            return final[0]["summary_text"].strip()

        return combined

    except Exception as exc:
        logger.error("Summarization failed: %s", exc)
        return None
