"""
ai_engine.agents.router
~~~~~~~~~~~~~~~~~~~~~~~~
Model router — selects the best LLM provider and model for a given user
request, considering:
  1. Explicit per-request model/provider override (highest priority)
  2. User's subscription plan (gating expensive models)
  3. Daily budget consumption (auto-fallback at 80%)
  4. Provider availability (key presence)

TASK-004-B8 (budget routing) + TASK-302 (multi-provider)

Budget thresholds:
  < 80%  — use the primary model (configured via MODEL_PRIMARY env var)
  80–99% — fall back to cheaper model (MODEL_FALLBACK env var)
  100%+  — block entirely (raise BudgetExceededError)

Usage:
    from ai_engine.agents.router import get_model_for_user, resolve_provider_model

    # Budget-aware model selection
    model_name = get_model_for_user(user_id="user-123", role="user")

    # Full resolution with per-request override
    provider, model = resolve_provider_model(
        requested_provider="anthropic",
        requested_model="claude-3-5-sonnet-20241022",
        user_id="user-123",
        role="pro",
    )
"""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# ── Model catalogue ────────────────────────────────────────────────────────────

# Supported providers
PROVIDERS = ("auto", "openai", "anthropic", "ollama", "gemini")

# Primary model per role (OpenRouter / OpenAI)
PRIMARY_MODELS: dict[str, str] = {
    "user": os.environ.get("MODEL_PRIMARY", "gpt-4o"),
    "pro": os.environ.get("MODEL_PRO", "gpt-4o"),
    "enterprise": os.environ.get("MODEL_ENT", "gpt-4o"),
    "staff": os.environ.get("MODEL_STAFF", "gpt-4o"),
}

# Fallback model (used when 80%+ budget consumed)
FALLBACK_MODELS: dict[str, str] = {
    "user": os.environ.get("MODEL_FALLBACK", "gpt-4o-mini"),
    "pro": os.environ.get("MODEL_FALLBACK_PRO", "gpt-4o-mini"),
    "enterprise": os.environ.get("MODEL_FALLBACK_ENT", "gpt-4o-mini"),
    "staff": os.environ.get("MODEL_FALLBACK_STAFF", "gpt-4o-mini"),
}

# Anthropic Claude models
CLAUDE_PRIMARY = os.environ.get("CLAUDE_MODEL_PRIMARY", "claude-3-5-sonnet-20241022")
CLAUDE_FALLBACK = os.environ.get("CLAUDE_MODEL_FALLBACK", "claude-3-haiku-20240307")

# Ollama local models
OLLAMA_DEFAULT = os.environ.get("OLLAMA_MODEL", "llama3.2")

# Plan-gated model permissions — which plans can request each provider
# Free users may only use cheap/local models; Pro and above can use all
PLAN_ALLOWED_PROVIDERS: dict[str, list[str]] = {
    "user": ["auto", "openai", "gemini", "ollama"],  # no Anthropic for free tier
    "pro": ["auto", "openai", "gemini", "ollama", "anthropic"],
    "enterprise": ["auto", "openai", "gemini", "ollama", "anthropic"],
    "staff": ["auto", "openai", "gemini", "ollama", "anthropic"],
}

# Budget threshold at which to switch to fallback
FALLBACK_THRESHOLD = float(os.environ.get("BUDGET_FALLBACK_THRESHOLD", "0.80"))


# ── Full provider+model resolution (TASK-302) ──────────────────────────────────


def resolve_provider_model(
    requested_provider: Optional[str] = None,
    requested_model: Optional[str] = None,
    user_id: Optional[str] = None,
    role: str = "user",
) -> tuple[str, str]:
    """
    Resolve the final (provider, model) pair for a request.

    Rules (in priority order):
      1. Explicit requested_provider + requested_model — honoured if plan allows it
      2. Plan gating — free users cannot use Anthropic; override to 'auto'
      3. Budget gating — if 80%+ consumed, switch to fallback model of same provider
      4. Auto-detect provider from model name prefix (claude-* → anthropic, etc.)

    Args:
        requested_provider: Provider hint from request ("anthropic", "ollama", etc.)
        requested_model:    Model name hint from request.
        user_id:            User ID for budget lookup.
        role:               Plan role for permission checks.

    Returns:
        (provider, model) tuple — both are non-empty strings.
    """
    provider = (requested_provider or "auto").lower().strip()
    model = requested_model or ""

    # ── Auto-detect provider from model name ──────────────────────────────
    if provider == "auto" and model:
        if model.startswith("claude-"):
            provider = "anthropic"
        elif (
            model.startswith("ollama/")
            or "/" not in model
            and not model.startswith("gpt")
        ):
            # Heuristic: unqualified short names → try Ollama
            pass
        elif model.startswith("gemini"):
            provider = "gemini"

    # ── Plan gating ───────────────────────────────────────────────────────
    allowed = PLAN_ALLOWED_PROVIDERS.get(role, PLAN_ALLOWED_PROVIDERS["user"])
    if provider not in allowed:
        logger.warning(
            "provider_gated role=%s requested_provider=%s allowed=%s — falling back to auto",
            role,
            provider,
            allowed,
        )
        provider = "auto"
        model = ""

    # ── Budget gating ─────────────────────────────────────────────────────
    budget_pct = _get_budget_percent(user_id, role) if user_id else 0.0
    if budget_pct >= 1.0:
        from ai_engine.middleware.rate_limit import (
            BudgetExceededError,
            get_budget_status,
        )

        info = get_budget_status(user_id or "", role) if user_id else {}
        raise BudgetExceededError(
            used_cents=info.get("used_cents", 0),
            limit_cents=info.get("limit_cents", 0),
            reset_at=_get_reset_time(),
        )

    use_fallback = budget_pct >= FALLBACK_THRESHOLD

    # ── Resolve model from provider ───────────────────────────────────────
    if provider == "anthropic":
        resolved_model = model or (CLAUDE_FALLBACK if use_fallback else CLAUDE_PRIMARY)
    elif provider == "ollama":
        resolved_model = model or OLLAMA_DEFAULT
    elif provider == "gemini":
        resolved_model = model or os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
    else:
        # openai / auto / openrouter
        provider = "openai"
        if model:
            resolved_model = model
        elif use_fallback:
            resolved_model = FALLBACK_MODELS.get(role, FALLBACK_MODELS["user"])
        else:
            resolved_model = PRIMARY_MODELS.get(role, PRIMARY_MODELS["user"])

    if use_fallback:
        logger.info(
            "model_fallback user=%s role=%s budget_pct=%.0f%% provider=%s model=%s",
            user_id,
            role,
            budget_pct * 100,
            provider,
            resolved_model,
        )

    return provider, resolved_model


# ── Available models catalogue (GET /models/) ──────────────────────────────────


def get_available_models(role: str = "user") -> list[dict]:
    """
    Return a catalogue of available models filtered by the user's plan.

    Used by the GET /models/ endpoint to populate the frontend model selector.
    """
    anthropic_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    ollama_url = bool(os.environ.get("OLLAMA_BASE_URL"))
    openrouter_key = bool(os.environ.get("OPENROUTER_API_KEY"))
    gemini_key = bool(os.environ.get("GEMINI_API_KEY"))

    allowed_providers = PLAN_ALLOWED_PROVIDERS.get(role, PLAN_ALLOWED_PROVIDERS["user"])

    catalogue = []

    # OpenAI / OpenRouter models
    if "openai" in allowed_providers or "auto" in allowed_providers:
        if openrouter_key:
            catalogue += [
                {
                    "id": "gpt-4o",
                    "name": "GPT-4o",
                    "provider": "openai",
                    "cost_tier": "standard",
                    "capabilities": ["chat", "code", "reasoning", "vision"],
                    "available": True,
                },
                {
                    "id": "gpt-4o-mini",
                    "name": "GPT-4o Mini",
                    "provider": "openai",
                    "cost_tier": "budget",
                    "capabilities": ["chat", "code"],
                    "available": True,
                },
            ]

    # Anthropic Claude models
    if "anthropic" in allowed_providers and anthropic_key:
        catalogue += [
            {
                "id": "claude-3-5-sonnet-20241022",
                "name": "Claude 3.5 Sonnet",
                "provider": "anthropic",
                "cost_tier": "standard",
                "capabilities": ["chat", "code", "reasoning", "long-context"],
                "available": True,
            },
            {
                "id": "claude-3-5-haiku-20241022",
                "name": "Claude 3.5 Haiku",
                "provider": "anthropic",
                "cost_tier": "budget",
                "capabilities": ["chat", "code"],
                "available": True,
            },
            {
                "id": "claude-3-haiku-20240307",
                "name": "Claude 3 Haiku",
                "provider": "anthropic",
                "cost_tier": "budget",
                "capabilities": ["chat", "code"],
                "available": True,
            },
        ]

    # Google Gemini
    if "gemini" in allowed_providers and gemini_key:
        catalogue += [
            {
                "id": "gemini-2.0-flash",
                "name": "Gemini 2.0 Flash",
                "provider": "gemini",
                "cost_tier": "budget",
                "capabilities": ["chat", "code", "vision"],
                "available": True,
            },
            {
                "id": "gemini-1.5-pro",
                "name": "Gemini 1.5 Pro",
                "provider": "gemini",
                "cost_tier": "standard",
                "capabilities": ["chat", "code", "long-context"],
                "available": True,
            },
        ]

    # Ollama local models
    if "ollama" in allowed_providers and ollama_url:
        ollama_models = os.environ.get(
            "OLLAMA_AVAILABLE_MODELS", "llama3.2,mistral,codellama"
        ).split(",")
        for m in ollama_models:
            m = m.strip()
            if m:
                catalogue.append(
                    {
                        "id": m,
                        "name": m.title().replace("-", " ").replace(".", " "),
                        "provider": "ollama",
                        "cost_tier": "free",
                        "capabilities": ["chat", "code"],
                        "available": True,
                    }
                )

    return catalogue


# ── Public API ─────────────────────────────────────────────────────────────────


def get_model_for_user(
    user_id: Optional[str] = None,
    role: str = "user",
    provider: str = "openai",
) -> str:
    """
    Return the best available LLM model name for the given user.

    If the user has consumed >= FALLBACK_THRESHOLD (80%) of their daily budget,
    automatically returns the fallback (cheaper) model. If budget is fully
    exhausted, raises BudgetExceededError.

    Args:
        user_id:  The user's identifier (used to look up Redis budget).
        role:     Plan role: "user" (free), "pro", "enterprise", "staff".
        provider: "openai" or "anthropic". Defaults to "openai".

    Returns:
        Model name string, e.g. "gpt-4o" or "gpt-4o-mini".

    Raises:
        BudgetExceededError: If daily budget is 100% consumed.
    """
    if not user_id:
        # No user context — return default primary model
        return _primary(role, provider)

    budget_pct = _get_budget_percent(user_id, role)

    if budget_pct >= 1.0:
        # Fully exhausted — raise with correct constructor signature
        from ai_engine.middleware.rate_limit import (
            BudgetExceededError,
            get_budget_status,
        )

        info = get_budget_status(user_id, role)
        raise BudgetExceededError(
            used_cents=info.get("used_cents", 0),
            limit_cents=info.get("limit_cents", 0),
            reset_at=_get_reset_time(),
        )

    if budget_pct >= FALLBACK_THRESHOLD:
        model = _fallback(role, provider)
        logger.info(
            "model_fallback user=%s role=%s budget_pct=%.0f%% model=%s",
            user_id,
            role,
            budget_pct * 100,
            model,
        )
        return model

    model = _primary(role, provider)
    logger.debug(
        "model_primary user=%s role=%s budget_pct=%.0f%% model=%s",
        user_id,
        role,
        budget_pct * 100,
        model,
    )
    return model


def get_model_info(user_id: Optional[str] = None, role: str = "user") -> dict:
    """
    Return a dict describing which model will be used and why.
    Useful for debugging and API responses.
    """
    budget_pct = _get_budget_percent(user_id, role) if user_id else 0.0
    exhausted = budget_pct >= 1.0
    fallback = budget_pct >= FALLBACK_THRESHOLD

    return {
        "model": _fallback(role) if fallback else _primary(role),
        "is_fallback": fallback,
        "is_exhausted": exhausted,
        "budget_percent": round(budget_pct * 100, 1),
        "threshold_pct": int(FALLBACK_THRESHOLD * 100),
        "primary_model": _primary(role),
        "fallback_model": _fallback(role),
    }


# ── Internal helpers ──────────────────────────────────────────────────────────


def _primary(role: str = "user", provider: str = "openai") -> str:
    if provider == "anthropic":
        return CLAUDE_PRIMARY
    return PRIMARY_MODELS.get(role, PRIMARY_MODELS["user"])


def _fallback(role: str = "user", provider: str = "openai") -> str:
    if provider == "anthropic":
        return CLAUDE_FALLBACK
    return FALLBACK_MODELS.get(role, FALLBACK_MODELS["user"])


def _get_budget_percent(user_id: str, role: str) -> float:
    """
    Return the fraction of daily budget consumed (0.0 – 1.0+).
    Returns 0.0 if Redis is unavailable or budget tracking not configured.
    """
    try:
        from ai_engine.middleware.rate_limit import get_budget_status

        info = get_budget_status(user_id, role)
        if info.get("unlimited"):
            return 0.0
        # get_budget_status returns "used_cents" (not "spent_cents")
        spent = info.get("used_cents", 0)
        limit = info.get("limit_cents", 1)
        return spent / max(limit, 1)
    except Exception as exc:
        logger.debug("budget_percent_unavailable: %s", exc)
        return 0.0


def _get_reset_time() -> str:
    """Return ISO-format UTC midnight (budget reset time)."""
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    reset = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return reset.isoformat()
