"""
Tests for TASK-302 — Claude + Ollama LLM Support (multi-model router)

Covers:
  - resolve_provider_model(): explicit provider, auto-detection, plan gating, budget fallback
  - get_available_models(): catalogue filtered by plan
  - get_model_for_user(): budget-aware legacy helper (unchanged behaviour)
  - SynapseAgent._build_llm(): provider dispatch for anthropic, ollama, gemini, auto
"""

import os
from unittest.mock import MagicMock, patch

import pytest

# ── resolve_provider_model tests ──────────────────────────────────────────────


class TestResolveProviderModel:

    def test_explicit_anthropic_pro_user(self):
        """Pro user can request Anthropic and gets Claude primary model."""
        from ai_engine.agents.router import CLAUDE_PRIMARY, resolve_provider_model

        with patch("ai_engine.agents.router._get_budget_percent", return_value=0.0):
            provider, model = resolve_provider_model(
                requested_provider="anthropic",
                requested_model="",
                user_id="user-123",
                role="pro",
            )

        assert provider == "anthropic"
        assert model == CLAUDE_PRIMARY

    def test_explicit_model_overrides_provider(self):
        """Explicit model name is returned as-is when plan allows provider."""
        from ai_engine.agents.router import resolve_provider_model

        with patch("ai_engine.agents.router._get_budget_percent", return_value=0.0):
            provider, model = resolve_provider_model(
                requested_provider="anthropic",
                requested_model="claude-3-haiku-20240307",
                role="pro",
            )

        assert provider == "anthropic"
        assert model == "claude-3-haiku-20240307"

    def test_free_user_anthropic_is_gated(self):
        """Free user requesting Anthropic is downgraded to auto/openai."""
        from ai_engine.agents.router import resolve_provider_model

        with patch("ai_engine.agents.router._get_budget_percent", return_value=0.0):
            provider, model = resolve_provider_model(
                requested_provider="anthropic",
                requested_model="claude-3-5-sonnet-20241022",
                role="user",  # free tier
            )

        # Plan gate kicks in — falls back to openai/auto
        assert provider == "openai"

    def test_ollama_any_plan(self):
        """Any plan can request Ollama (local, free)."""
        from ai_engine.agents.router import OLLAMA_DEFAULT, resolve_provider_model

        with patch("ai_engine.agents.router._get_budget_percent", return_value=0.0):
            provider, model = resolve_provider_model(
                requested_provider="ollama",
                role="user",
            )

        assert provider == "ollama"
        assert model == OLLAMA_DEFAULT

    def test_budget_fallback_switches_to_cheaper_model(self):
        """At 80%+ budget, model falls back to cheaper variant."""
        from ai_engine.agents.router import FALLBACK_MODELS, resolve_provider_model

        with patch("ai_engine.agents.router._get_budget_percent", return_value=0.85):
            provider, model = resolve_provider_model(
                user_id="user-123",
                role="user",
            )

        assert model == FALLBACK_MODELS["user"]

    def test_budget_exhausted_raises(self):
        """At 100% budget, an exception is raised (BudgetExceededError or similar)."""
        from ai_engine.agents.router import resolve_provider_model
        from ai_engine.middleware.rate_limit import BudgetExceededError

        with patch("ai_engine.agents.router._get_budget_percent", return_value=1.0):
            with pytest.raises((BudgetExceededError, Exception)):
                resolve_provider_model(user_id="user-123", role="user")

    def test_auto_detects_claude_from_model_name(self):
        """provider='auto' + model starting with 'claude-' → anthropic."""
        from ai_engine.agents.router import resolve_provider_model

        with patch("ai_engine.agents.router._get_budget_percent", return_value=0.0):
            provider, model = resolve_provider_model(
                requested_provider="auto",
                requested_model="claude-3-5-sonnet-20241022",
                role="pro",
            )

        assert provider == "anthropic"
        assert model == "claude-3-5-sonnet-20241022"

    def test_gemini_provider_explicit(self):
        """Explicit gemini provider returns gemini model."""
        from ai_engine.agents.router import resolve_provider_model

        with patch("ai_engine.agents.router._get_budget_percent", return_value=0.0):
            provider, model = resolve_provider_model(
                requested_provider="gemini",
                requested_model="gemini-2.0-flash",
                role="user",
            )

        assert provider == "gemini"
        assert model == "gemini-2.0-flash"

    def test_no_user_returns_primary(self):
        """No user_id (anonymous) returns primary model without budget check."""
        from ai_engine.agents.router import PRIMARY_MODELS, resolve_provider_model

        provider, model = resolve_provider_model(role="user")
        assert provider == "openai"
        assert model == PRIMARY_MODELS["user"]

    def test_anthropic_budget_fallback_to_haiku(self):
        """Anthropic + high budget → falls back to CLAUDE_FALLBACK."""
        from ai_engine.agents.router import CLAUDE_FALLBACK, resolve_provider_model

        with patch("ai_engine.agents.router._get_budget_percent", return_value=0.9):
            provider, model = resolve_provider_model(
                requested_provider="anthropic",
                user_id="user-123",
                role="pro",
            )

        assert provider == "anthropic"
        assert model == CLAUDE_FALLBACK


# ── get_available_models tests ────────────────────────────────────────────────


class TestGetAvailableModels:

    def test_free_user_no_anthropic(self):
        """Free plan catalogue does not include Anthropic models."""
        from ai_engine.agents.router import get_available_models

        with patch.dict(
            os.environ,
            {
                "ANTHROPIC_API_KEY": "test-key",
                "OPENROUTER_API_KEY": "test-key",
            },
        ):
            models = get_available_models(role="user")

        providers = {m["provider"] for m in models}
        assert "anthropic" not in providers

    def test_pro_user_gets_anthropic(self):
        """Pro plan catalogue includes Anthropic models when key is set."""
        from ai_engine.agents.router import get_available_models

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            models = get_available_models(role="pro")

        providers = {m["provider"] for m in models}
        assert "anthropic" in providers

    def test_ollama_models_when_configured(self):
        """Ollama models appear when OLLAMA_BASE_URL is set."""
        from ai_engine.agents.router import get_available_models

        with patch.dict(
            os.environ,
            {
                "OLLAMA_BASE_URL": "http://localhost:11434",
                "OLLAMA_AVAILABLE_MODELS": "llama3.2,mistral",
            },
        ):
            models = get_available_models(role="user")

        ollama_models = [m for m in models if m["provider"] == "ollama"]
        assert len(ollama_models) >= 2
        ids = [m["id"] for m in ollama_models]
        assert "llama3.2" in ids
        assert "mistral" in ids

    def test_ollama_models_not_shown_when_not_configured(self):
        """Ollama models don't appear when OLLAMA_BASE_URL is not set."""
        from ai_engine.agents.router import get_available_models

        env = {k: v for k, v in os.environ.items() if k != "OLLAMA_BASE_URL"}
        with patch.dict(os.environ, env, clear=True):
            models = get_available_models(role="user")

        ollama_models = [m for m in models if m["provider"] == "ollama"]
        assert len(ollama_models) == 0

    def test_all_models_have_required_fields(self):
        """Each model in the catalogue has required fields."""
        from ai_engine.agents.router import get_available_models

        with patch.dict(
            os.environ,
            {
                "ANTHROPIC_API_KEY": "k",
                "OPENROUTER_API_KEY": "k",
                "OLLAMA_BASE_URL": "http://localhost:11434",
            },
        ):
            models = get_available_models(role="pro")

        for m in models:
            assert "id" in m
            assert "name" in m
            assert "provider" in m
            assert "cost_tier" in m
            assert "capabilities" in m
            assert isinstance(m["capabilities"], list)


# ── SynapseAgent._build_llm tests ─────────────────────────────────────────────


class TestSynapseAgentBuildLLM:

    def _make_agent(self, provider="auto", model_name="gemini-1.5-flash-latest", **env):
        """Helper to create a SynapseAgent with a mocked LLM."""
        from ai_engine.agents.base import SynapseAgent

        with patch.dict(os.environ, env):
            # Patch _build_llm to avoid needing real API keys
            with patch.object(SynapseAgent, "_build_llm", return_value=MagicMock()):
                agent = SynapseAgent(tools=[], provider=provider, model_name=model_name)
        return agent

    def test_anthropic_raises_without_key(self):
        """Anthropic provider raises ValueError when no API key."""
        from ai_engine.agents.base import SynapseAgent

        env = {
            k: v
            for k, v in os.environ.items()
            if k not in ("ANTHROPIC_API_KEY", "OPENROUTER_API_KEY", "GEMINI_API_KEY")
        }
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
                SynapseAgent(tools=[], provider="anthropic")

    def test_anthropic_raises_without_package(self):
        """Anthropic provider raises ImportError when langchain-anthropic not installed."""
        from ai_engine.agents import base as base_mod

        with (
            patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}),
            patch.object(base_mod, "_ANTHROPIC_AVAILABLE", False),
            patch.object(base_mod, "_ChatAnthropic", None),
        ):
            with pytest.raises((ImportError, ValueError)):
                base_mod.SynapseAgent(tools=[], provider="anthropic")

    def test_ollama_raises_without_package(self):
        """Ollama provider raises ImportError when langchain-ollama not installed."""
        from ai_engine.agents import base as base_mod

        with (
            patch.object(base_mod, "_OLLAMA_AVAILABLE", False),
            patch.object(base_mod, "_ChatOllama", None),
        ):
            with pytest.raises((ImportError, ValueError)):
                base_mod.SynapseAgent(tools=[], provider="ollama")

    def test_anthropic_uses_claude_model(self):
        """Anthropic provider selects CLAUDE_MODEL_PRIMARY when no explicit model.

        QA-24: _build_llm now delegates to llm_factory.build_llm(), so we patch
        the factory rather than base_mod._ChatAnthropic.
        """
        import ai_engine.agents.llm_factory as factory_mod

        mock_anthropic = MagicMock()
        mock_instance = MagicMock()
        mock_anthropic.return_value = mock_instance

        with (
            patch.dict(
                os.environ,
                {
                    "ANTHROPIC_API_KEY": "test-key",
                    "CLAUDE_MODEL_PRIMARY": "claude-test-model",
                },
            ),
            patch.object(factory_mod, "_ANTHROPIC_AVAILABLE", True),
            patch.object(factory_mod, "ChatAnthropic", mock_anthropic),
        ):
            from ai_engine.agents.base import SynapseAgent

            agent = SynapseAgent(tools=[], provider="anthropic")

        mock_anthropic.assert_called_once()
        call_kwargs = mock_anthropic.call_args[1]
        assert call_kwargs.get("model") == "claude-test-model"

    def test_provider_attribute_stored(self):
        """SynapseAgent stores the provider attribute correctly."""
        agent = self._make_agent(provider="anthropic")
        assert agent.provider == "anthropic"

    def test_auto_falls_back_to_openrouter(self):
        """Auto provider with OPENROUTER_API_KEY uses OpenRouter.

        QA-24: _build_llm now delegates to llm_factory.build_llm(), so we patch
        the factory module instead of base_mod._ChatOpenAI.
        """
        import ai_engine.agents.llm_factory as factory_mod

        mock_openai = MagicMock()
        mock_instance = MagicMock()
        mock_openai.return_value = mock_instance

        with (
            patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}),
            patch.object(factory_mod, "_OPENAI_AVAILABLE", True),
            patch.object(factory_mod, "ChatOpenAI", mock_openai),
        ):
            from ai_engine.agents.base import SynapseAgent

            agent = SynapseAgent(tools=[], provider="auto")

        mock_openai.assert_called_once()

    def test_no_provider_raises(self):
        """Auto with no keys configured raises ValueError."""
        from ai_engine.agents import base as base_mod

        env = {
            k: v
            for k, v in os.environ.items()
            if k not in ("ANTHROPIC_API_KEY", "OPENROUTER_API_KEY", "GEMINI_API_KEY")
        }
        with (
            patch.dict(os.environ, env, clear=True),
            patch.object(base_mod, "_OPENAI_AVAILABLE", True),
            patch.object(base_mod, "_ChatOpenAI", None),
        ):
            with pytest.raises(ValueError, match="No LLM configured"):
                base_mod.SynapseAgent(tools=[], provider="auto")
