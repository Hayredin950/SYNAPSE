"""
ai_engine.agents.llm_factory
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Shared LLM factory used by both the RAG chain (rag/chain.py) and the
agent executor (agents/base.py). Consolidates duplicate _build_llm()
implementations into a single, tested function.

QA-24: Previously both SynapseRAGChain._build_llm() and SynapseAgent._build_llm()
contained near-identical provider-routing logic. Any change had to be made in two
places. This module is the single source of truth.

Provider selection order:
  1. provider="anthropic"     → Claude         (ANTHROPIC_API_KEY required)
  2. provider="ollama"        → Ollama         (no API key; OLLAMA_BASE_URL)
  3. provider="gemini"        → Gemini         (GEMINI_API_KEY required)
  4. provider="scitely"       → Scitely        (SCITELY_API_KEY; OpenAI-compatible)
  5. provider="openai"        → OpenRouter     (OPENROUTER_API_KEY)
  6. provider="ai_gateway"    → Vercel AI GW   (AI_GATEWAY_API_KEY)
  7. provider="groq"          → Groq           (GROQ_API_KEY)
  8. provider="nvidia"        → NVIDIA NIM     (NVIDIA_API_KEY; OpenAI-compatible)
  9. provider="auto"          → AI Gateway → Groq → NVIDIA → OpenRouter → Scitely
                                 → Gemini → ValueError if none configured

For runtime resilience use :func:`build_llm_with_fallbacks` instead — it
returns the same kind of object but transparently fails over to the next
configured provider when one is rate-limited or down. Free-tier quotas are hit
routinely, so agent and RAG paths should prefer it.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ── Optional package guards ────────────────────────────────────────────────────
try:
    from langchain_openai import ChatOpenAI  # type: ignore

    _OPENAI_AVAILABLE = True
except ImportError:
    ChatOpenAI = None  # type: ignore[assignment,misc]
    _OPENAI_AVAILABLE = False

try:
    from langchain_anthropic import ChatAnthropic  # type: ignore

    _ANTHROPIC_AVAILABLE = True
except ImportError:
    ChatAnthropic = None  # type: ignore[assignment,misc]
    _ANTHROPIC_AVAILABLE = False

try:
    from langchain_ollama import ChatOllama  # type: ignore

    _OLLAMA_AVAILABLE = True
except ImportError:
    ChatOllama = None  # type: ignore[assignment,misc]
    _OLLAMA_AVAILABLE = False


def build_llm(
    provider: str = "auto",
    model: str = "",
    temperature: float = 0.2,
    max_tokens: int = 1024,
    streaming: bool = False,
    # Per-user API key overrides (take priority over env vars)
    scitely_api_key: Optional[str] = None,
    openrouter_api_key: Optional[str] = None,
    gemini_api_key: Optional[str] = None,
    anthropic_api_key: Optional[str] = None,
    ollama_base_url: Optional[str] = None,
    # New providers (Apr 2026): server-side keys, no per-user key UI yet.
    ai_gateway_api_key: Optional[str] = None,
    groq_api_key: Optional[str] = None,
    nvidia_api_key: Optional[str] = None,
) -> Any:
    """
    Instantiate and return an LLM for the given provider.

    Args:
        provider:           LLM provider — "auto"|"openai"|"anthropic"|"ollama"|"gemini"
        model:              Model name override. Falls back to env vars per provider.
        temperature:        Sampling temperature (0–1).
        max_tokens:         Maximum tokens in the response.
        streaming:          Whether to enable streaming mode.
        openrouter_api_key: Per-user OpenRouter key (overrides OPENROUTER_API_KEY env).
        scitely_api_key:    Per-user Scitely key (overrides SCITELY_API_KEY env).
        gemini_api_key:     Per-user Gemini key (overrides GEMINI_API_KEY env).
        anthropic_api_key:  Per-user Anthropic key (overrides ANTHROPIC_API_KEY env).
        ollama_base_url:    Per-user Ollama base URL (overrides OLLAMA_BASE_URL env).

    Returns:
        A LangChain chat model instance.

    Raises:
        ValueError:   If the required API key is missing.
        ImportError:  If the required package is not installed.
    """

    # ── Anthropic Claude ──────────────────────────────────────────────────────
    if provider == "anthropic":
        key = anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if not key:
            raise ValueError("ANTHROPIC_API_KEY is required for provider='anthropic'.")
        if not _ANTHROPIC_AVAILABLE or ChatAnthropic is None:
            raise ImportError(
                "langchain-anthropic is not installed. "
                "Install it with: pip install langchain-anthropic"
            )
        resolved = model or os.environ.get(
            "CLAUDE_MODEL_PRIMARY", "claude-3-5-sonnet-20241022"
        )
        logger.info(
            "llm_factory provider=anthropic model=%s streaming=%s", resolved, streaming
        )
        return ChatAnthropic(
            model=resolved,
            temperature=temperature,
            max_tokens=max_tokens,
            anthropic_api_key=key,
            streaming=streaming,
        )

    # ── Ollama (local) ────────────────────────────────────────────────────────
    if provider == "ollama":
        if not _OLLAMA_AVAILABLE or ChatOllama is None:
            raise ImportError(
                "langchain-ollama is not installed. "
                "Install it with: pip install langchain-ollama"
            )
        base = ollama_base_url or os.environ.get(
            "OLLAMA_BASE_URL", "http://localhost:11434"
        )
        resolved = model or os.environ.get("OLLAMA_MODEL", "llama3.2")
        logger.info("llm_factory provider=ollama model=%s base_url=%s", resolved, base)
        return ChatOllama(
            model=resolved,
            base_url=base,
            temperature=temperature,
            num_predict=max_tokens,
        )

    # ── Google Gemini (explicit) ──────────────────────────────────────────────
    if provider == "gemini":
        key = gemini_api_key or os.environ.get("GEMINI_API_KEY", "")
        if not key:
            raise ValueError(
                "API key not configured for standard agents. Please add a Gemini key in Settings → AI Engine."
            )
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI  # type: ignore
        except ImportError as exc:
            raise ImportError(
                "langchain-google-genai is not installed. "
                "Install it with: pip install langchain-google-genai"
            ) from exc
        resolved = model or os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
        logger.info(
            "llm_factory provider=gemini model=%s streaming=%s", resolved, streaming
        )
        return ChatGoogleGenerativeAI(
            model=resolved,
            temperature=temperature,
            max_output_tokens=max_tokens,
            google_api_key=key,
            streaming=streaming,
            convert_system_message_to_human=True,
        )

    # ── Vercel AI Gateway (explicit or auto-fallback) ─────────────────────────
    # OpenAI-compatible — uses ChatOpenAI with the Gateway base URL.
    # Default model is small/fast Anthropic via Gateway; override via AI_GATEWAY_MODEL
    # or by passing `model="..."` (e.g. "openai/gpt-5-mini", "google/gemini-3-flash").
    gw_key = ai_gateway_api_key or os.environ.get("AI_GATEWAY_API_KEY", "")
    gw_base = os.environ.get(
        "AI_GATEWAY_BASE_URL", "https://ai-gateway.vercel.sh/v1"
    )
    gw_model = model or os.environ.get(
        "AI_GATEWAY_MODEL", "anthropic/claude-haiku-4.5"
    )

    if provider == "ai_gateway":
        if not gw_key:
            raise ValueError(
                "AI_GATEWAY_API_KEY is required for provider='ai_gateway'."
            )
        if not _OPENAI_AVAILABLE or ChatOpenAI is None:
            raise ImportError("langchain-openai is not installed.")
        logger.info(
            "llm_factory provider=ai_gateway model=%s streaming=%s",
            gw_model,
            streaming,
        )
        return ChatOpenAI(
            model=gw_model,
            temperature=temperature,
            max_tokens=max_tokens,
            openai_api_key=gw_key,
            openai_api_base=gw_base,
            streaming=streaming,
            default_headers={
                "HTTP-Referer": "https://synapse.ai",
                "X-Title": "SYNAPSE",
            },
        )

    # ── Groq (explicit or auto-fallback) ──────────────────────────────────────
    # OpenAI-compatible — extremely fast inference via Groq's LPU hardware.
    groq_key = groq_api_key or os.environ.get("GROQ_API_KEY", "")
    groq_base = os.environ.get("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
    groq_model = model or os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

    if provider == "groq":
        if not groq_key:
            raise ValueError("GROQ_API_KEY is required for provider='groq'.")
        if not _OPENAI_AVAILABLE or ChatOpenAI is None:
            raise ImportError("langchain-openai is not installed.")
        logger.info(
            "llm_factory provider=groq model=%s streaming=%s",
            groq_model,
            streaming,
        )
        return ChatOpenAI(
            model=groq_model,
            temperature=temperature,
            max_tokens=max_tokens,
            openai_api_key=groq_key,
            openai_api_base=groq_base,
            streaming=streaming,
        )

    # ── NVIDIA NIM (explicit or auto-fallback) ────────────────────────────────
    # OpenAI-compatible. Free hosted endpoints for open-weight models; the
    # nemotron/mistral-nemotron families are tuned for tool calling, which is
    # what the ReAct agent loop needs.
    nv_key = nvidia_api_key or os.environ.get("NVIDIA_API_KEY", "")
    nv_base = os.environ.get("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
    nv_model = model or os.environ.get(
        "NVIDIA_MODEL", "mistralai/mistral-nemotron"
    )

    if provider == "nvidia":
        if not nv_key:
            raise ValueError("NVIDIA_API_KEY is required for provider='nvidia'.")
        if not _OPENAI_AVAILABLE or ChatOpenAI is None:
            raise ImportError("langchain-openai is not installed.")
        logger.info(
            "llm_factory provider=nvidia model=%s streaming=%s", nv_model, streaming
        )
        return ChatOpenAI(
            model=nv_model,
            temperature=temperature,
            max_tokens=max_tokens,
            openai_api_key=nv_key,
            openai_api_base=nv_base,
            streaming=streaming,
        )

    # In auto mode, prefer the new server-side providers FIRST.
    # Priority 0: Replit built-in OpenAI proxy — no user key needed.
    replit_key = os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY", "")
    replit_base = os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL", "")
    replit_model = model or os.environ.get("REPLIT_AI_MODEL", "gpt-4o-mini")
    if replit_key and replit_base and _OPENAI_AVAILABLE and ChatOpenAI is not None:
        logger.info(
            "llm_factory provider=replit_openai model=%s streaming=%s",
            replit_model,
            streaming,
        )
        return ChatOpenAI(
            model=replit_model,
            temperature=temperature,
            max_tokens=max_tokens,
            openai_api_key=replit_key,
            openai_api_base=replit_base,
            streaming=streaming,
        )

    # Priority 1+: AI Gateway → Groq → OpenRouter → Scitely → Gemini
    if gw_key and _OPENAI_AVAILABLE and ChatOpenAI is not None:
        logger.info(
            "llm_factory provider=ai_gateway_auto model=%s streaming=%s",
            gw_model,
            streaming,
        )
        return ChatOpenAI(
            model=gw_model,
            temperature=temperature,
            max_tokens=max_tokens,
            openai_api_key=gw_key,
            openai_api_base=gw_base,
            streaming=streaming,
            default_headers={
                "HTTP-Referer": "https://synapse.ai",
                "X-Title": "SYNAPSE",
            },
        )

    if groq_key and _OPENAI_AVAILABLE and ChatOpenAI is not None:
        logger.info(
            "llm_factory provider=groq_auto model=%s streaming=%s",
            groq_model,
            streaming,
        )
        return ChatOpenAI(
            model=groq_model,
            temperature=temperature,
            max_tokens=max_tokens,
            openai_api_key=groq_key,
            openai_api_base=groq_base,
            streaming=streaming,
        )

    if nv_key and _OPENAI_AVAILABLE and ChatOpenAI is not None:
        logger.info(
            "llm_factory provider=nvidia_auto model=%s streaming=%s",
            nv_model,
            streaming,
        )
        return ChatOpenAI(
            model=nv_model,
            temperature=temperature,
            max_tokens=max_tokens,
            openai_api_key=nv_key,
            openai_api_base=nv_base,
            streaming=streaming,
        )

    # ── OpenRouter / OpenAI (explicit or auto-fallback) ───────────────────────
    or_key = openrouter_api_key or os.environ.get("OPENROUTER_API_KEY", "")
    or_base = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    or_model = model or os.environ.get(
        "OPENROUTER_MODEL", "google/gemini-2.0-flash-001"
    )

    if or_key and _OPENAI_AVAILABLE and ChatOpenAI is not None:
        logger.info(
            "llm_factory provider=openrouter model=%s streaming=%s", or_model, streaming
        )
        return ChatOpenAI(
            model=or_model,
            temperature=temperature,
            max_tokens=max_tokens,
            openai_api_key=or_key,
            openai_api_base=or_base,
            streaming=streaming,
            default_headers={
                "HTTP-Referer": "https://synapse.ai",
                "X-Title": "SYNAPSE",
            },
        )

    # ── Scitely (explicit or auto-fallback) ────────────────────────────────────
    sc_key = scitely_api_key or os.environ.get("SCITELY_API_KEY", "")
    sc_base = "https://api.scitely.com/v1"
    sc_model = model or os.environ.get("SCITELY_MODEL", "deepseek-v3")

    if provider == "scitely":
        if not sc_key:
            raise ValueError("SCITELY_API_KEY is required for provider='scitely'.")
        if not _OPENAI_AVAILABLE or ChatOpenAI is None:
            raise ImportError("langchain-openai is not installed.")
        logger.info(
            "llm_factory provider=scitely model=%s streaming=%s", sc_model, streaming
        )
        return ChatOpenAI(
            model=sc_model,
            temperature=temperature,
            max_tokens=max_tokens,
            openai_api_key=sc_key,
            openai_api_base=sc_base,
            streaming=streaming,
            default_headers={
                "HTTP-Referer": "https://synapse.ai",
                "X-Title": "SYNAPSE",
            },
        )

    # Auto-fallback: try Scitely (only if OpenRouter failed or key missing)
    if sc_key and _OPENAI_AVAILABLE and ChatOpenAI is not None:
        logger.info(
            "llm_factory provider=scitely_auto model=%s streaming=%s",
            sc_model,
            streaming,
        )
        return ChatOpenAI(
            model=sc_model,
            temperature=temperature,
            max_tokens=max_tokens,
            openai_api_key=sc_key,
            openai_api_base=sc_base,
            streaming=streaming,
            default_headers={
                "HTTP-Referer": "https://synapse.ai",
                "X-Title": "SYNAPSE",
            },
        )

    # ── Gemini auto-fallback ──────────────────────────────────────────────────
    gem_key = gemini_api_key or os.environ.get("GEMINI_API_KEY", "")
    if gem_key:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI  # type: ignore

            resolved = model or os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
            logger.info(
                "llm_factory provider=gemini_auto model=%s streaming=%s",
                resolved,
                streaming,
            )
            return ChatGoogleGenerativeAI(
                model=resolved,
                temperature=temperature,
                max_output_tokens=max_tokens,
                google_api_key=gem_key,
                streaming=streaming,
                convert_system_message_to_human=True,
            )
        except ImportError:
            pass

    raise ValueError(
        "No AI provider configured. Set one of AI_GATEWAY_API_KEY, GROQ_API_KEY, "
        "SCITELY_API_KEY, OPENROUTER_API_KEY, or GEMINI_API_KEY on the server, "
        "or add a personal key in Settings → AI Engine."
    )


# ── Runtime fallback chain ─────────────────────────────────────────────────────
#
# build_llm() picks ONE provider when the object is constructed. If that
# provider is rate-limited at call time — which is the normal steady state on
# free tiers, not an edge case — the request just fails.
#
# build_llm_with_fallbacks() instead returns a runnable that transparently
# retries the next configured provider on failure. Each provider has an
# independent quota pool, so a 429 on Groq is survivable if Gemini is
# configured.
#
# Order is cheapest-and-fastest first:
#   Groq (14.4k req/day free) → NVIDIA NIM → Gemini (1k/day) → OpenRouter
#   → Scitely/DeepSeek (paid overflow)

# Providers tried in order, when a key is present for them.
_FALLBACK_ORDER = ("groq", "nvidia", "gemini", "openai", "scitely")

# Env var that must be non-empty for a provider to participate.
_PROVIDER_KEY_ENV = {
    "groq": "GROQ_API_KEY",
    "nvidia": "NVIDIA_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "openai": "OPENROUTER_API_KEY",
    "scitely": "SCITELY_API_KEY",
    "ai_gateway": "AI_GATEWAY_API_KEY",
}


def _configured_providers(**key_overrides: Optional[str]) -> list[str]:
    """Return the fallback-order providers that have a usable key."""
    available = []
    for name in _FALLBACK_ORDER:
        override = key_overrides.get(f"{name}_api_key")
        if override or os.environ.get(_PROVIDER_KEY_ENV.get(name, ""), ""):
            available.append(name)
    return available


def build_llm_with_fallbacks(
    provider: str = "auto",
    model: str = "",
    temperature: float = 0.2,
    max_tokens: int = 1024,
    streaming: bool = False,
    max_retries_per_provider: int = 2,
    **key_overrides: Optional[str],
) -> Any:
    """
    Build an LLM that fails over to the next configured provider on error.

    Behaves exactly like :func:`build_llm` when `provider` is explicit (the
    caller asked for a specific provider, so silently using a different one
    would be wrong) or when only one provider is configured.

    Each provider is also retried with exponential backoff before moving on,
    which absorbs the short-lived 429s that per-minute rate limits produce.

    Returns:
        A LangChain runnable. Raises the last provider's error if all fail.
    """
    # Explicit provider request → no substituting a different one.
    if provider != "auto":
        primary = build_llm(
            provider=provider,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            streaming=streaming,
            **key_overrides,  # type: ignore[arg-type]
        )
        return primary.with_retry(stop_after_attempt=max_retries_per_provider)

    available = _configured_providers(**key_overrides)

    # None of the ordered providers is configured (e.g. only AI Gateway or the
    # Replit proxy). Defer to build_llm's own auto priority.
    if not available:
        primary = build_llm(
            provider="auto",
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            streaming=streaming,
            **key_overrides,  # type: ignore[arg-type]
        )
        return primary.with_retry(stop_after_attempt=max_retries_per_provider)

    # Build each configured provider in order. The first becomes the primary
    # and the rest become fallbacks — a provider must never appear in its own
    # fallback list, or a 429 would just retry the exhausted quota.
    built: list[Any] = []
    for name in available:
        try:
            built.append(
                build_llm(
                    provider=name,
                    # Only the primary honours an explicit model override;
                    # fallbacks use their own provider-appropriate default.
                    model=model if not built else "",
                    temperature=temperature,
                    max_tokens=max_tokens,
                    streaming=streaming,
                    **key_overrides,  # type: ignore[arg-type]
                ).with_retry(stop_after_attempt=max_retries_per_provider)
            )
        except (ValueError, ImportError) as exc:
            logger.debug("llm_factory provider %s unavailable: %s", name, exc)

    if not built:
        raise ValueError(
            "No AI provider could be constructed. Check that the configured "
            "provider's client package is installed."
        )

    primary, fallbacks = built[0], built[1:]
    if not fallbacks:
        return primary

    logger.info(
        "llm_factory fallback chain active: %s",
        " → ".join(available[: len(built)]),
    )
    return primary.with_fallbacks(fallbacks)
