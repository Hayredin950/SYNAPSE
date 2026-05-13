"""
Named Entity Recognition (NER) for the SYNAPSE NLP pipeline.

Uses spaCy's ``en_core_web_sm`` model to extract entities from text.
The focus is on technology-relevant entity types: organisations, products,
proper nouns that could be technology terms, and people in tech news.

The spaCy model is loaded lazily and cached for the lifetime of the process.
"""

import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

# spaCy entity types to keep
RELEVANT_ENTITY_TYPES: set = {
    "ORG",  # Companies, organisations (e.g. OpenAI, Google)
    "PRODUCT",  # Software, hardware products
    "PERSON",  # Individuals mentioned in tech articles
    "GPE",  # Geopolitical entities (countries, cities)
    "WORK_OF_ART",  # Named works; sometimes captures project names
    "LAW",  # Standards, regulations
    "EVENT",  # Named events (conferences, releases)
    "LANGUAGE",  # Programming/spoken language names
    "NORP",  # Nationalities, political groups (for trend context)
}

# Module-level cache
_nlp = None


def _get_nlp():
    """Lazy-load and cache the spaCy model."""
    global _nlp
    if _nlp is None:
        try:
            import spacy  # noqa: PLC0415

            logger.info("Loading spaCy model: en_core_web_sm")
            _nlp = spacy.load("en_core_web_sm")
            logger.info("spaCy model loaded successfully.")
        except OSError:
            logger.error(
                "spaCy model 'en_core_web_sm' not found. "
                "Run: python -m spacy download en_core_web_sm"
            )
            _nlp = None
        except Exception as exc:
            logger.error("Failed to load spaCy model: %s", exc)
            _nlp = None
    return _nlp


def extract_entities(text: str) -> List[Dict[str, str]]:
    """
    Extract named entities from *text* using spaCy NER.

    Args:
        text: Plain-text document.

    Returns:
        List of entity dicts, each with keys ``"text"``, ``"label"``, and
        ``"start"``/``"end"`` character offsets.  Example::

            [{"text": "OpenAI", "label": "ORG", "start": 0, "end": 6}, …]

        Returns an empty list if the model is unavailable or text is empty.
    """
    if not text:
        return []

    nlp = _get_nlp()
    if nlp is None:
        return []

    try:
        # Process at most 100 000 characters to avoid memory issues
        doc = nlp(text[:100_000])
        entities = []
        seen: set = set()

        for ent in doc.ents:
            if ent.label_ not in RELEVANT_ENTITY_TYPES:
                continue
            key = (ent.text.strip().lower(), ent.label_)
            if key in seen:
                continue
            seen.add(key)
            entities.append(
                {
                    "text": ent.text.strip(),
                    "label": ent.label_,
                    "start": ent.start_char,
                    "end": ent.end_char,
                }
            )

        return entities

    except Exception as exc:
        logger.error("NER extraction failed: %s", exc)
        return []


def extract_tech_terms(text: str) -> List[str]:
    """
    Return a flat list of unique technology-relevant entity strings.

    Convenience wrapper around :func:`extract_entities` that returns only
    the entity text values, deduplicated and sorted alphabetically.

    Args:
        text: Plain-text document.

    Returns:
        Sorted list of unique entity strings.
    """
    entities = extract_entities(text)
    return sorted({e["text"] for e in entities})
