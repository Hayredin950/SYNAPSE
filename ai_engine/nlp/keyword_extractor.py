"""
Keyword extraction for the SYNAPSE NLP pipeline.

Combines two complementary approaches:

1. **KeyBERT** — uses ``all-MiniLM-L6-v2`` sentence embeddings to select
   keywords that are semantically close to the document.
2. **YAKE** — a statistical, language-agnostic extractor that is fast and
   does not require a model download.

Results from both methods are merged, deduplicated, and returned ranked by
relevance score (higher = more relevant).
"""

import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)

# Keyphrase length bounds
MIN_NGRAM: int = 1
MAX_NGRAM: int = 2

# Number of keywords each extractor produces before merging
TOP_N_EACH: int = 15

# Final number of keywords returned after merging both lists
TOP_N_FINAL: int = 10


def _extract_keybert(text: str, top_n: int) -> List[Tuple[str, float]]:
    """
    Extract keywords using KeyBERT with all-MiniLM-L6-v2.

    Args:
        text:  Document text.
        top_n: Number of keywords to extract.

    Returns:
        List of ``(keyword, score)`` tuples, score in [0, 1].
    """
    try:
        from keybert import KeyBERT  # noqa: PLC0415

        kw_model = KeyBERT(model="all-MiniLM-L6-v2")
        results = kw_model.extract_keywords(
            text,
            keyphrase_ngram_range=(MIN_NGRAM, MAX_NGRAM),
            stop_words="english",
            top_n=top_n,
            use_mmr=True,  # Maximal Marginal Relevance for diversity
            diversity=0.5,
        )
        return [(kw, round(score, 4)) for kw, score in results]
    except Exception as exc:
        logger.warning("KeyBERT extraction failed: %s", exc)
        return []


def _extract_yake(text: str, top_n: int) -> List[Tuple[str, float]]:
    """
    Extract keywords using YAKE (statistical, no model required).

    YAKE scores are *lower* = more relevant; we invert them so that the
    merged list uses the same high-is-better convention as KeyBERT.

    Args:
        text:  Document text.
        top_n: Number of keywords to extract.

    Returns:
        List of ``(keyword, score)`` tuples, score in [0, 1] (higher = better).
    """
    try:
        import yake  # noqa: PLC0415

        extractor = yake.KeywordExtractor(
            lan="en",
            n=MAX_NGRAM,
            dedupLim=0.7,
            top=top_n,
            features=None,
        )
        raw = extractor.extract_keywords(text)
        if not raw:
            return []
        # Invert: raw scores are 0 (best) → ∞ (worst).  Normalise to [0, 1].
        max_score = max(score for _, score in raw) or 1.0
        return [(kw, round(1.0 - score / max_score, 4)) for kw, score in raw]
    except Exception as exc:
        logger.warning("YAKE extraction failed: %s", exc)
        return []


def extract_keywords(text: str, top_n: int = TOP_N_FINAL) -> List[str]:
    """
    Extract the top *top_n* keywords from *text* using KeyBERT + YAKE.

    Both extractors are run and their results are merged.  When a keyword
    appears in both lists its scores are averaged, giving it a higher final
    rank.  The merged list is sorted descending by score and the top *top_n*
    keywords are returned as plain strings.

    Args:
        text:  Plain-text document (HTML should be stripped beforehand).
        top_n: Number of keywords to return (default 10).

    Returns:
        Ordered list of keyword strings (most relevant first).
    """
    if not text or len(text.split()) < 10:
        return []

    keybert_kws = _extract_keybert(text, TOP_N_EACH)
    yake_kws = _extract_yake(text, TOP_N_EACH)

    # Merge: accumulate scores per keyword (case-insensitive key)
    merged: dict = {}
    for kw, score in keybert_kws + yake_kws:
        key = kw.lower().strip()
        if not key:
            continue
        if key in merged:
            # Average when seen in both extractors
            merged[key] = (merged[key] + score) / 2
        else:
            merged[key] = score

    # Sort by score descending
    ranked = sorted(merged.items(), key=lambda x: x[1], reverse=True)
    return [kw for kw, _ in ranked[:top_n]]
