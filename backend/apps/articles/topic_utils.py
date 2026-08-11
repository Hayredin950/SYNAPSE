"""
Lightweight, zero-cost topic classification for articles.

Classifies an article into a small set of canonical, user-facing topics
(AI, Web Dev, Security, Cloud, DevOps, Research, Programming, Open Source)
using deterministic keyword rules over the title + excerpt/content.

Deliberately does NOT call an LLM or a ML model — it runs instantly and free
on every scrape (in fetch_article_excerpt) and in one-off backfills, so the
Tech Feed topic filters work without burning tokens.
"""

from __future__ import annotations

# Canonical topics — these match the Tech Feed filter pills.
CANONICAL_TOPICS: tuple = (
    "AI",
    "Web Dev",
    "Security",
    "Cloud",
    "DevOps",
    "Research",
    "Programming",
    "Open Source",
)

FALLBACK_TOPIC = "Technology"

# Rules are evaluated in order — first match wins. More specific topics
# (AI, Security) come before broader ones (Programming, Open Source).
TOPIC_RULES: tuple = (
    (
        "AI",
        (
            "artificial intelligence",
            "machine learning",
            "deep learning",
            "neural network",
            "llm",
            "large language model",
            "chatgpt",
            "openai",
            "gpt-",
            "claude",
            "gemini",
            "anthropic",
            "transformer",
            "diffusion model",
            "generative ai",
            "hugging face",
            "fine-tun",
            "tensorflow",
            "pytorch",
            "langchain",
            "ai agent",
            "ai model",
            "ai ",
            "ai-",
            "rag",
            "embeddings",
            "inference",
            "copilot",
        ),
    ),
    (
        "Security",
        (
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
            "foia",
            "privacy",
            "leak",
            "threat",
        ),
    ),
    (
        "Web Dev",
        (
            "web dev",
            "web development",
            "javascript",
            "typescript",
            "react",
            "next.js",
            "nextjs",
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
            "html5",
        ),
    ),
    (
        "DevOps",
        (
            "devops",
            "ci/cd",
            "continuous integration",
            "continuous delivery",
            "github actions",
            "gitlab ci",
            "docker",
            "kubernetes",
            "k8s",
            "container",
            "monitoring",
            "observability",
            "sre",
            "site reliability",
            "uptime",
            "deploy",
            "deployment pipeline",
            "infrastructure as code",
        ),
    ),
    (
        "Cloud",
        (
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
            "hosting",
            "datacenter",
            "postgres",
            "database",
            "redis",
            "cdn",
            "bandwidth",
            "undersea cable",
        ),
    ),
    (
        "Research",
        (
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
        ),
    ),
    (
        "Open Source",
        (
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
        ),
    ),
    (
        "Programming",
        (
            "programming",
            "developer",
            "coding",
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
            "database",
        ),
    ),
)

# Synonyms so the topic filter still matches legacy / NLP-pipeline values
# (e.g. stored topic "Artificial Intelligence" matches the "AI" pill).
TOPIC_ALIASES: dict = {
    "ai": [
        "ai",
        "artificial intelligence",
        "machine learning",
        "deep learning",
        "data science",
        "ml",
        "llm",
        "ai/ml",
    ],
    "web dev": ["web dev", "web development", "web", "frontend", "javascript"],
    "security": ["security", "cybersecurity", "infosec", "information security"],
    "cloud": ["cloud", "cloud computing"],
    "devops": ["devops"],
    "research": ["research", "science", "academic", "research paper"],
    "programming": ["programming", "software engineering", "software"],
    "open source": ["open source", "opensource"],
}


def classify_topic_keywords(title: str = "", text: str = "") -> str:
    """Return the canonical topic for an article, or ``FALLBACK_TOPIC``."""
    combined = f"{title} {text}".lower()
    if not combined.strip():
        return FALLBACK_TOPIC
    for topic, keywords in TOPIC_RULES:
        for kw in keywords:
            if kw in combined:
                return topic
    return FALLBACK_TOPIC


def is_meaningful_topic(topic: str) -> bool:
    """True when the topic is one users can filter by (not a generic fallback)."""
    return topic in CANONICAL_TOPICS
