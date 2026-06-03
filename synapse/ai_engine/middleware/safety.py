"""
SYNAPSE Safety Middleware
-------------------------
Detects jailbreak attempts and common prompt injection patterns.
Applied before every LLM call in the AI engine.
"""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# ── Jailbreak pattern detection ───────────────────────────────────────────────
# Common patterns used to bypass AI safety measures
_JAILBREAK_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions?|prompts?|rules?|directives?)",
    r"(system\s+prompt|system\s+override|admin\s+mode|developer\s+mode)",
    r"pretend\s+(you\s+are|to\s+be|you're)\s+(an?\s+)?(evil|unrestricted|jailbroken|DAN|GPT-?4?)",
    r"\bDAN\s+mode\b",
    r"(enable|activate|switch\s+to)\s+(jailbreak|unrestricted|no.?filter|DAN)",
    r"you\s+(are|were|will\s+be)\s+(now\s+)?(free|unfiltered|uncensored|without\s+(restrictions?|rules?))",
    r"forget\s+(everything|all)\s+(you\s+(were|have\s+been)\s+told|above)",
    r"(act|behave)\s+as\s+(if\s+)?(you\s+have\s+no|without\s+any)\s+(restrictions?|rules?|guidelines?)",
    r"disregard\s+(all\s+)?(your\s+)?(previous|prior)\s+(instructions?|guidelines?|rules?)",
]

_COMPILED_JAILBREAK = [
    re.compile(p, re.IGNORECASE | re.DOTALL) for p in _JAILBREAK_PATTERNS
]

# Soft-block phrases (warn but allow) vs hard-block (always refuse)
_HARD_BLOCK_PATTERNS = [
    r"generate\s+(malware|ransomware|virus|trojan|keylogger)",
    r"(step.by.step|instructions?|how\s+to)\s+(make|create|build|synthesize)\s+(a\s+)?(bomb|explosive|weapon|poison)",
    r"(CSAM|child\s+(sexual|explicit|pornograph))",
]
_COMPILED_HARD_BLOCK = [
    re.compile(p, re.IGNORECASE | re.DOTALL) for p in _HARD_BLOCK_PATTERNS
]


class JailbreakDetectedError(Exception):
    """Raised when a jailbreak attempt is detected."""

    def __init__(self, pattern: str, hard_block: bool = False):
        self.pattern = pattern
        self.hard_block = hard_block
        super().__init__(
            f"{'Hard-blocked' if hard_block else 'Jailbreak'} pattern detected: {pattern}"
        )


def check_jailbreak(text: str, user_id: Optional[str] = None) -> None:
    """
    Scan input text for jailbreak / prompt injection patterns.
    Raises JailbreakDetectedError if a pattern matches.
    Logs the attempt for abuse review.
    """
    # Hard block check first
    for pattern in _COMPILED_HARD_BLOCK:
        if pattern.search(text):
            logger.warning(
                "HARD BLOCK: user=%s matched pattern='%s' input_excerpt='%.100s'",
                user_id,
                pattern.pattern[:60],
                text,
            )
            raise JailbreakDetectedError(pattern=pattern.pattern, hard_block=True)

    # Soft jailbreak check
    for pattern in _COMPILED_JAILBREAK:
        if pattern.search(text):
            logger.warning(
                "JAILBREAK ATTEMPT: user=%s matched pattern='%s' input_excerpt='%.100s'",
                user_id,
                pattern.pattern[:60],
                text,
            )
            raise JailbreakDetectedError(pattern=pattern.pattern, hard_block=False)


def check_pii(text: str, user_id: Optional[str] = None) -> dict:
    """
    Detect PII in user input using Microsoft Presidio.
    Returns a dict with detected entities.
    Logs any PII detected (for abuse review) but does NOT raise — caller decides.

    Requires: pip install presidio-analyzer presidio-anonymizer

    TASK-004-B6
    """
    try:
        from presidio_analyzer import AnalyzerEngine  # type: ignore

        analyzer = AnalyzerEngine()
        results = analyzer.analyze(text=text, language="en")
        if results:
            entities = [
                {
                    "type": r.entity_type,
                    "start": r.start,
                    "end": r.end,
                    "score": round(r.score, 3),
                }
                for r in results
                if r.score >= 0.7
            ]
            if entities:
                logger.warning(
                    "PII_DETECTED: user=%s entities=%s input_excerpt='%.60s'",
                    user_id,
                    [e["type"] for e in entities],
                    text,
                )
                return {"pii_detected": True, "entities": entities}
        return {"pii_detected": False, "entities": []}
    except ImportError:
        # presidio not installed — skip silently
        return {"pii_detected": False, "entities": []}
    except Exception as exc:
        logger.debug("PII check error (skipping): %s", exc)
        return {"pii_detected": False, "entities": []}


def redact_pii(text: str) -> str:
    """
    Redact PII from text using Presidio Anonymizer.
    Returns redacted text, or original text if Presidio not available.

    TASK-004-B6
    """
    try:
        from presidio_analyzer import AnalyzerEngine  # type: ignore
        from presidio_anonymizer import AnonymizerEngine  # type: ignore

        analyzer = AnalyzerEngine()
        anonymizer = AnonymizerEngine()
        results = analyzer.analyze(text=text, language="en")
        if results:
            return anonymizer.anonymize(text=text, analyzer_results=results).text
        return text
    except ImportError:
        return text
    except Exception:
        return text


def sanitize_input(text: str, max_length: int = 8192) -> str:
    """
    Basic input sanitisation:
    - Truncate to max_length
    - Strip null bytes
    - Normalise whitespace
    """
    if not text:
        return ""
    text = text.replace("\x00", "")  # Remove null bytes
    text = text[:max_length]
    return text.strip()
