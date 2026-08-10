"""
ai_engine.lite
~~~~~~~~~~~~~~
SYNAPSE Lite Mode — run the full app on a small / free box (2 GB RAM).

Normal mode loads several local ML models into memory at once:
    torch + transformers  (~1.5–2 GB base)
    BAAI/bge-large-en-v1.5 (embeddings, ~1.3 GB)
    facebook/bart-large-cnn  (summarizer, ~1.6 GB)
    facebook/bart-large-mnli (topic classifier, ~1.6 GB)
    cardiffnlp/twitter-roberta-base-sentiment (~500 MB)
    spaCy en_core_web_sm  (NER, ~100 MB)

That is ~6–8 GB before Django, Postgres, Redis and Celery — the reason the
full stack needs a 4–8 GB box.

When ``SYNAPSE_LITE=1`` is set, every one of those models is skipped. The
small NLP jobs they did are delegated to the free cloud LLM/embedding APIs
the app already calls (Groq → NVIDIA NIM → Gemini). torch/transformers/
sentence-transformers/spaCy are never imported, so the backend's resident
memory drops to a normal Django app (~1–2 GB total with Postgres + Redis).

This module is deliberately dependency-light (stdlib + httpx) so it can be
imported from any of the three images (backend, ai-engine, scraper) without
pulling in the ML stack.

Toggle:
    SYNAPSE_LITE=1   → lite mode (API-based NLP + embeddings)
    SYNAPSE_LITE=0   → full mode (local models, default)

Individual components can also be switched independently:
    EMBEDDING_PROVIDER=api    → embeddings via NVIDIA NIM (default in lite)
    EMBEDDING_PROVIDER=local  → local sentence-transformers (default in full)
"""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_TRUE_VALUES = ("1", "true", "yes", "on")


def is_lite_mode() -> bool:
    """
    Return True when SYNAPSE Lite mode is enabled.

    Reads ``SYNAPSE_LITE`` from the environment. Accepts the common truthy
    spellings: ``1``, ``true``, ``yes``, ``on``. Anything else (including
    unset) means full mode.
    """
    return os.environ.get("SYNAPSE_LITE", "0").strip().lower() in _TRUE_VALUES


def lite_mode_label() -> str:
    """Human-readable label for logs/health endpoints."""
    return "lite" if is_lite_mode() else "full"


# ── LLM completion helper (OpenAI-compatible, httpx only) ─────────────────────
#
# Used by the lite-mode summarizer / topic classifier / sentiment analyzer.
# Tries each configured provider in order and returns the first successful
# text completion. Each provider has an independent quota pool, so a 429 on
# Groq is survivable if NVIDIA or Gemini is configured — the same fallback
# philosophy as ai_engine.agents.llm_factory, minus the langchain dependency.

_LLM_PROVIDERS = (
    # (name, base_url, model_env, key_env, default_model)
    (
        "groq",
        "https://api.groq.com/openai/v1",
        "GROQ_MODEL",
        "GROQ_API_KEY",
        "llama-3.3-70b-versatile",
    ),
    (
        "nvidia",
        "https://integrate.api.nvidia.com/v1",
        "NVIDIA_MODEL",
        "NVIDIA_API_KEY",
        "mistralai/mistral-nemotron",
    ),
)


def llm_complete(
    prompt: str,
    system: Optional[str] = None,
    max_tokens: int = 400,
    temperature: float = 0.2,
    timeout: float = 45.0,
) -> Optional[str]:
    """
    Run a single non-streaming completion against the first available provider.

    Provider order (when a key is present): Groq → NVIDIA NIM → Gemini REST.

    Args:
        prompt:      The user-turn text to complete.
        system:      Optional system prompt (first message).
        max_tokens:  Maximum completion tokens.
        temperature: Sampling temperature.
        timeout:     Per-request timeout in seconds.

    Returns:
        The completion text, or ``None`` when every provider fails
        (no key configured, network error, rate limit, …). Callers must
        degrade gracefully on ``None``.
    """
    import httpx  # noqa: PLC0415

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    for name, base_url, model_env, key_env, default_model in _LLM_PROVIDERS:
        api_key = os.environ.get(key_env, "").strip()
        if not api_key:
            continue
        model = os.environ.get(model_env, "").strip() or default_model
        try:
            resp = httpx.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
                timeout=timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            content = (data.get("choices") or [{}])[0].get("message", {}).get("content")
            if content and str(content).strip():
                return str(content).strip()
            logger.warning("lite.llm_complete: empty completion from %s", name)
        except Exception as exc:
            logger.warning("lite.llm_complete: provider=%s failed: %s", name, exc)

    # ── Gemini REST fallback (its API is not OpenAI-compatible) ──────────────
    gem_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if gem_key:
        gem_model = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash").strip()
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{gem_model}:generateContent?key={gem_key}"
        )
        # Gemini's generateContent has no "system" role; the messages list
        # already carries any system text as the first part, which the model
        # still sees as instruction context in the prompt.
        parts = [{"text": m["content"]} for m in messages]
        try:
            resp = httpx.post(
                url,
                json={"contents": [{"role": "user", "parts": parts}]},
                timeout=timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            try:
                text = data["candidates"][0]["content"]["parts"][0]["text"]
            except (KeyError, IndexError, TypeError):
                text = None
            if text and str(text).strip():
                return str(text).strip()
            logger.warning("lite.llm_complete: empty completion from gemini")
        except Exception as exc:
            logger.warning("lite.llm_complete: provider=gemini failed: %s", exc)

    return None
