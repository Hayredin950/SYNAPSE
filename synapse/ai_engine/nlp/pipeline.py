"""
Main NLP processing pipeline for SYNAPSE.

Orchestrates all NLP steps in sequence:
  1. Text cleaning
  2. Language detection  (skip non-English)
  3. Keyword extraction  (KeyBERT + YAKE)
  4. Topic classification (zero-shot BART)
  5. Sentiment analysis  (RoBERTa)
  6. Named Entity Recognition (spaCy)
  7. Summarization        (BART facebook/bart-large-cnn)  ← Phase 2.2

Returns a structured NLPResult dataclass that the Celery task uses to
update the Article model fields.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .cleaner import clean_text
from .keyword_extractor import extract_keywords
from .language_detector import detect_language, is_english
from .ner import extract_entities
from .sentiment_analyzer import analyze_sentiment, sentiment_to_score
from .topic_classifier import classify_topic

logger = logging.getLogger(__name__)


@dataclass
class NLPResult:
    """Structured output from the NLP pipeline."""

    language: str = "unknown"
    language_confidence: float = 0.0
    is_english: bool = False
    keywords: List[str] = field(default_factory=list)
    topic: str = ""
    topic_confidence: float = 0.0
    sentiment_label: str = "NEUTRAL"
    sentiment_score: Optional[float] = None  # signed float in [-1, 1]
    entities: List[Dict] = field(default_factory=list)
    summary: Optional[str] = None  # BART-generated summary (Phase 2.2)
    skipped: bool = False
    skip_reason: str = ""
    error: str = ""


def run_pipeline(
    text: str,
    title: str = "",
    run_keywords: bool = True,
    run_topic: bool = True,
    run_sentiment: bool = True,
    run_ner: bool = True,
    run_summarization: bool = True,
) -> NLPResult:
    """
    Run the full NLP pipeline on *text*.

    Combines title + content for richer signal when extracting keywords,
    topics, and entities.  Sentiment is analysed on content only.

    Args:
        text:             Raw article content (may contain HTML).
        title:            Article title (prepended to NLP input for context).
        run_keywords:     Whether to run keyword extraction.
        run_topic:        Whether to run topic classification.
        run_sentiment:    Whether to run sentiment analysis.
        run_ner:          Whether to run named entity recognition.
        run_summarization: Whether to run BART summarization (Phase 2.2).

    Returns:
        :class:`NLPResult` populated with all extracted fields.
    """
    result = NLPResult()

    # ── 1. Clean text ────────────────────────────────────────────────────────
    try:
        clean = clean_text(text, strip_html=True)
        if title:
            full_text = f"{title.strip()}. {clean}"
        else:
            full_text = clean
    except Exception as exc:
        result.error = f"Text cleaning failed: {exc}"
        result.skipped = True
        result.skip_reason = "cleaning_error"
        logger.error("NLP pipeline: text cleaning failed: %s", exc)
        return result

    if not clean or len(clean.split()) < 5:
        result.skipped = True
        result.skip_reason = "text_too_short"
        logger.debug("NLP pipeline: text too short, skipping.")
        return result

    # ── 2. Language detection ────────────────────────────────────────────────
    try:
        lang, lang_conf = detect_language(clean[:1000])
        result.language = lang
        result.language_confidence = lang_conf
        result.is_english = lang == "en" and lang_conf >= 0.80

        if not result.is_english:
            result.skipped = True
            result.skip_reason = f"non_english:{lang}:{lang_conf}"
            logger.info(
                "NLP pipeline: skipping non-English content (lang=%s, conf=%.2f).",
                lang,
                lang_conf,
            )
            return result
    except Exception as exc:
        logger.warning("NLP pipeline: language detection failed: %s", exc)
        # Assume English and continue

    # ── 3. Keyword extraction ────────────────────────────────────────────────
    if run_keywords:
        try:
            result.keywords = extract_keywords(full_text, top_n=10)
            logger.debug("Keywords: %s", result.keywords)
        except Exception as exc:
            logger.warning("NLP pipeline: keyword extraction failed: %s", exc)

    # ── 4. Topic classification ──────────────────────────────────────────────
    if run_topic:
        try:
            topic, topic_conf = classify_topic(full_text[:2000])
            result.topic = topic
            result.topic_confidence = topic_conf
            logger.debug("Topic: %s (%.2f)", topic, topic_conf)
        except Exception as exc:
            logger.warning("NLP pipeline: topic classification failed: %s", exc)

    # ── 5. Sentiment analysis ────────────────────────────────────────────────
    if run_sentiment:
        try:
            label, confidence = analyze_sentiment(clean)
            result.sentiment_label = label
            result.sentiment_score = sentiment_to_score(label, confidence)
            logger.debug("Sentiment: %s (score=%.4f)", label, result.sentiment_score)
        except Exception as exc:
            logger.warning("NLP pipeline: sentiment analysis failed: %s", exc)

    # ── 6. Named Entity Recognition ─────────────────────────────────────────
    if run_ner:
        try:
            result.entities = extract_entities(full_text)
            logger.debug("Entities found: %d", len(result.entities))
        except Exception as exc:
            logger.warning("NLP pipeline: NER failed: %s", exc)

    # ── 7. Summarization (BART) ─────────────────────────────────────────────
    # Phase 2.2: Auto-run BART summarization as part of the pipeline.
    # Uses the article content (clean) rather than full_text to avoid
    # title duplication in the generated summary.
    if run_summarization:
        try:
            from .summarizer import summarize  # noqa: PLC0415

            result.summary = summarize(clean)
            logger.debug(
                "Summary generated (%d chars).",
                len(result.summary) if result.summary else 0,
            )
        except Exception as exc:
            logger.warning("NLP pipeline: summarization failed: %s", exc)

    return result
