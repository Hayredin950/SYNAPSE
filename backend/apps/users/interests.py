"""
Shared interest personalization maps.

These maps power every personalized surface in SYNAPSE:

  * The Tech Feed "For You" tab (?for_you=1)
  * The home page "Latest from Tech Feed / Trending on GitHub / ..." sections
  * The daily briefing tasks

Interests are stored as canonical slugs (see OnboardingPreferences.INTEREST_CHOICES)
e.g. "ai_ml", "web_dev". The InterestProfileBuilder frontend widget uses its own
topic ids (e.g. "ai", "web", "rust") — BUILDER_TOPIC_MAP converts them to slugs.

FEED_MATCH_SLUGS      → the canonical slug set supported by feed filtering.
INTEREST_TOPICS       → slug → canonical topic(s) (topic_utils.CANONICAL_TOPICS).
INTEREST_KEYWORDS     → slug → lowercase keyword phrases matched against
                        title/summary/content/tags.
"""

from __future__ import annotations

from typing import Iterable

# ── Interest Profile Builder topic ids → canonical onboarding slugs ──────────
BUILDER_TOPIC_MAP: dict = {
    "ai": "ai_ml",
    "web": "web_dev",
    "devops": "cloud_devops",
    "security": "security",
    "rust": "programming",
    "mobile": "mobile",
    "data": "data_science",
    "research": "research",
    "startup": "startup",
    "open_source": "open_source",
    "blockchain": "blockchain",
    "ux": "design_ux",
}

# Canonical slugs that the feed filters understand (superset of the onboarding
# wizard choices — the extra slugs come from the InterestProfileBuilder).
FEED_MATCH_SLUGS: frozenset = frozenset(
    {
        "ai_ml",
        "web_dev",
        "security",
        "cloud_devops",
        "research",
        "data_science",
        "open_source",
        "startup",
        "finance",
        "health_bio",
        "programming",
        "mobile",
        "blockchain",
        "design_ux",
    }
)

# slug → canonical topic(s) from articles.topic_utils.CANONICAL_TOPICS.
# An empty list means "keywords only" (no canonical topic exists for it).
INTEREST_TOPICS: dict = {
    "ai_ml": ["AI"],
    "web_dev": ["Web Dev"],
    "security": ["Security"],
    "cloud_devops": ["Cloud", "DevOps"],
    "research": ["Research"],
    "data_science": ["Research", "Programming"],
    "open_source": ["Open Source", "Programming"],
    "startup": [],
    "finance": [],
    "health_bio": [],
    "programming": ["Programming"],
    "mobile": ["Web Dev"],
    "blockchain": [],
    "design_ux": ["Web Dev"],
}

# slug → lowercase keyword phrases matched against title/summary/tags.
INTEREST_KEYWORDS: dict = {
    "ai_ml": [
        "machine learning",
        "artificial intelligence",
        "neural network",
        "deep learning",
        "llm",
        "gpt",
        "openai",
        "chatgpt",
        "claude",
        "anthropic",
        "gemini",
        "transformer",
        "diffusion model",
        "generative ai",
        "hugging face",
        "ai agent",
        "ai model",
        "embeddings",
        "inference",
        "copilot",
        "pytorch",
        "tensorflow",
        "fine-tun",
        "rag",
    ],
    "web_dev": [
        "web development",
        "javascript",
        "typescript",
        "react",
        "next.js",
        "css",
        "html",
        "frontend",
        "front-end",
        "browser",
        "website",
        "web app",
        "npm",
        "tailwind",
        "svelte",
        "vue",
        "markdown editor",
        "static site",
    ],
    "security": [
        "security",
        "vulnerability",
        "exploit",
        "malware",
        "ransomware",
        "phishing",
        "cyber",
        "breach",
        "encryption",
        "zero-day",
        "backdoor",
        "ddos",
        "firewall",
        "hacking",
        "hacker",
        "password",
        "surveillance",
        "privacy",
        "leak",
        "threat",
    ],
    "cloud_devops": [
        "cloud",
        "aws",
        "azure",
        "google cloud",
        "gcp",
        "serverless",
        "lambda",
        "s3",
        "ec2",
        "terraform",
        "kubernetes",
        "docker",
        "container",
        "devops",
        "ci/cd",
        "github actions",
        "monitoring",
        "observability",
        "sre",
        "deploy",
        "infrastructure as code",
    ],
    "research": [
        "arxiv",
        "research paper",
        "preprint",
        "researchers",
        "study",
        "scientists",
        "academic",
        "university",
        "published in",
        "benchmark",
        "new paper",
        "paper shows",
        "thesis",
        "reproducib",
    ],
    "data_science": [
        "data science",
        "analytics",
        "big data",
        "pandas",
        "numpy",
        "jupyter",
        "statistics",
        "visualization",
        "data engineering",
    ],
    "open_source": [
        "open source",
        "open-source",
        "open source software",
        "github",
        "gitlab",
        "license",
        "gpl",
        "mit license",
        "self-host",
        "free and open",
    ],
    "startup": [
        "startup",
        "y combinator",
        "venture",
        "founder",
        "fundraising",
        "seed round",
        "series a",
        "entrepreneur",
    ],
    "finance": [
        "fintech",
        "crypto",
        "blockchain",
        "bitcoin",
        "ethereum",
        "finance",
        "banking",
        "stock market",
        "trading",
        "investing",
    ],
    "health_bio": [
        "health tech",
        "biotech",
        "medical",
        "clinical",
        "genomics",
        "dna",
        "drug",
        "bio",
        "healthcare",
    ],
    "programming": [
        "programming",
        "python",
        "rust",
        "golang",
        "c++",
        "compiler",
        "api",
        "framework",
        "library",
        "command line",
        "cli",
        "terminal",
        "code editor",
        "git",
        "software engineer",
        "refactor",
        "debug",
    ],
    "mobile": ["mobile", "ios", "android", "swift", "flutter", "react native"],
    "blockchain": [
        "blockchain",
        "web3",
        "crypto",
        "bitcoin",
        "ethereum",
        "defi",
        "smart contract",
        "nft",
    ],
    "design_ux": [
        "design",
        "ux",
        "ui",
        "accessibility",
        "figma",
        "prototype",
        "wireframe",
        "user experience",
    ],
}


def normalize_interest(raw: str) -> str:
    """Map a builder/display topic id to its canonical slug (identity if unknown)."""
    if not raw:
        return ""
    return BUILDER_TOPIC_MAP.get(raw.strip().lower(), raw.strip().lower())


def user_interest_slugs(user) -> list:
    """
    Return the effective personalization slugs for a user.

    Combines:
      * OnboardingPreferences.interests (canonical slugs)
      * user.preferences["interest_profile"]["topics"] (InterestProfileBuilder
        topic ids — normalized to slugs)

    Returns a de-duplicated list of canonical slugs. Empty when the user has
    no personalization data.
    """
    slugs: list = []
    seen: set = set()

    def _add(raw):
        slug = normalize_interest(raw)
        if slug and slug not in seen:
            seen.add(slug)
            slugs.append(slug)

    try:
        prefs = getattr(user, "onboarding_prefs", None)
        # Only completed onboarding interests count (a half-finished wizard
        # should not silently re-shape the feed).
        if prefs and getattr(prefs, "completed", False):
            for interest in (prefs.interests if prefs else []) or []:
                _add(interest)
    except Exception:
        pass

    try:
        profile = (getattr(user, "preferences", None) or {}).get("interest_profile", {})
        for topic in (profile.get("topics") if profile else []) or []:
            _add(topic)
    except Exception:
        pass

    return slugs


def apply_for_you_filter(
    qs, request=None, text_fields=None, topic_field="topic", user=None
):
    """
    Apply interest-based personalization to a queryset.

    Returns the filtered queryset, or the original queryset when:
      * no user is provided (anonymous) or no ?for_you=1 is requested
      * the user has no personalization data
      * the filtered result would be empty (fall back to unfiltered)

    Shared by the articles / repositories / videos / tweets / papers list views
    and the briefing tasks, so the whole app personalizes consistently.

    Args:
        qs:           base queryset
        request:      optional DRF request — enables the ?for_you=1 gate
        text_fields:  model fields to run keyword matches on
        topic_field:  name of a simple topic string field, or None if the
                      model has no such field (JSON arrays, etc.)
        user:         explicit user (used when there is no request, e.g. tasks)
    """
    if text_fields is None:
        text_fields = ()

    # The ?for_you=1 gate: when a request is present, personalization is
    # opt-in via the query param (the home page sends it). When called from
    # a task with an explicit user, personalization is always on.
    if request is not None:
        for_you = request.GET.get("for_you") == "1"
        if not for_you:
            return qs
        user = user or getattr(request, "user", None)

    if user is None or not getattr(user, "is_authenticated", True):
        return qs

    try:
        slugs = user_interest_slugs(user)
        if not slugs:
            return qs
        interest_q = build_interest_q(
            slugs, text_fields=text_fields, topic_field=topic_field
        )
        # If nothing matches, fall back to unfiltered so users never see an
        # empty feed because of strict personalization.
        if not interest_q:
            return qs
        personalized = qs.filter(interest_q)
        if personalized.exists():
            return personalized
    except Exception:
        pass
    return qs


def build_interest_q(
    slugs: Iterable[str],
    text_fields: Iterable[str],
    topic_field: str = "topic",
):
    """
    Build a Django Q() that matches content for the given interest slugs.

    Matching strategy per slug:
      1. Canonical topic match (topic__iexact via TOPIC_ALIASES) — precise and
         fast, e.g. "AI" matches stored topic "AI".
      2. Keyword phrases via word-boundary case-insensitive regex on the given
         text fields. Boundaries matter: a plain icontains for short keywords
         like "rag" / "ui" / "api" / "git" matches unrelated words
         ("storage", "equipment", "capital", "digit"), which would flood the
         personalized feed with false positives. `\b…\b` keeps matches
         meaningful ("react" still matches "React" / "react-hooks").

    Args:
        slugs:        canonical interest slugs (or raw ids — normalized here).
        text_fields:  model fields to run keyword matches on
                      (e.g. ("title", "summary")).
        topic_field:  name of the topic field ("topic" for articles), or None
                      for models without a simple topic field.

    Returns:
        django.db.models.Q — empty Q() (matches nothing) when no slugs given.
    """
    import re  # noqa: PLC0415

    from apps.articles.topic_utils import TOPIC_ALIASES  # noqa: PLC0415

    from django.db.models import Q  # noqa: PLC0415

    combined = Q()
    for raw in slugs:
        slug = normalize_interest(raw)
        if not slug:
            continue

        # 1. Canonical topic matches (only for models with a simple topic field)
        if topic_field:
            for topic in INTEREST_TOPICS.get(slug, []):
                aliases = TOPIC_ALIASES.get(topic.lower(), [topic])
                for alias in aliases:
                    combined |= Q(**{f"{topic_field}__iexact": alias})

        # 2. Keyword phrase matches — one word-boundary regex per field
        #    (far fewer OR branches than per-keyword icontains).
        keywords = [k for k in INTEREST_KEYWORDS.get(slug, []) if k]
        if not keywords:
            continue
        pattern = r"\b(?:{})\b".format("|".join(re.escape(k) for k in keywords))
        for field in text_fields:
            combined |= Q(**{f"{field}__iregex": pattern})

    return combined
