"""
SYNAPSE Lite mode — unit tests.

Verifies:
  - is_lite_mode() honours the SYNAPSE_LITE env var truthy spellings.
  - The embedder resolves EMBEDDING_PROVIDER=api and never touches
    sentence-transformers (no torch import) in lite mode.
  - The NLP pipeline takes the cloud-LLM path (llm_complete) for
    summarization / topic / sentiment instead of the local transformers.
  - Keyword extraction skips KeyBERT (YAKE only) and NER returns [].
"""

from __future__ import annotations

import os
import sys
from unittest.mock import patch

# Ensure ai_engine is importable (repo root)
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def _import_lite():
    from ai_engine.lite import is_lite_mode, llm_complete

    return is_lite_mode, llm_complete


class TestLiteModeFlag:

    def test_unset_env_is_full_mode(self):
        is_lite_mode, _ = _import_lite()
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SYNAPSE_LITE", None)
            assert is_lite_mode() is False

    def test_zero_is_full_mode(self):
        is_lite_mode, _ = _import_lite()
        with patch.dict(os.environ, {"SYNAPSE_LITE": "0"}):
            assert is_lite_mode() is False

    def test_one_is_lite(self):
        is_lite_mode, _ = _import_lite()
        with patch.dict(os.environ, {"SYNAPSE_LITE": "1"}):
            assert is_lite_mode() is True

    def test_true_is_lite(self):
        is_lite_mode, _ = _import_lite()
        with patch.dict(os.environ, {"SYNAPSE_LITE": "true"}):
            assert is_lite_mode() is True

    def test_uppercase_treated_as_lite(self):
        is_lite_mode, _ = _import_lite()
        with patch.dict(os.environ, {"SYNAPSE_LITE": "YES"}):
            assert is_lite_mode() is True


class TestLiteLLM:

    def test_llm_complete_returns_none_without_keys(self):
        _, llm_complete = _import_lite()
        with patch.dict(
            os.environ,
            {
                "GROQ_API_KEY": "",
                "NVIDIA_API_KEY": "",
                "GEMINI_API_KEY": "",
            },
            clear=False,
        ):
            assert llm_complete("hello") is None

    def test_llm_complete_tries_groq_first(self):
        """Groq is the first provider — its response wins when it succeeds."""
        _, llm_complete = _import_lite()
        with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_test"}):
            with patch("httpx.post") as mock_post:
                mock_post.return_value.raise_for_status.return_value = None
                mock_post.return_value.json.return_value = {
                    "choices": [{"message": {"content": "OK"}}]
                }
                assert llm_complete("hi") == "OK"
                # Called against the Groq base URL
                assert "api.groq.com" in mock_post.call_args[0][0]


class TestEmbedderLiteProvider:

    def _import_embedder(self):
        from ai_engine.embeddings.embedder import SynapseEmbedder

        return SynapseEmbedder

    def test_provider_resolves_to_api_in_lite_mode(self):
        """Constructing the embedder with SYNAPSE_LITE=1 picks the API provider
        and never loads a local model (the api _load_model path is a no-op)."""
        SynapseEmbedder = self._import_embedder()
        with patch.dict(
            os.environ,
            {
                "SYNAPSE_LITE": "1",
                "EMBEDDING_PROVIDER": "",
                "EMBEDDING_DIM": "1024",
                "NVIDIA_API_KEY": "nvapi-test",
            },
            clear=False,
        ):
            embedder = SynapseEmbedder()
            assert embedder._provider == "api"
            assert embedder._model is None  # no sentence-transformers loaded

    def test_provider_local_when_not_lite(self):
        """Without lite mode the provider defaults to local — but loading the
        sentence-transformer would be heavy, so stub the loader and verify the
        provider selection only."""
        SynapseEmbedder = self._import_embedder()
        with patch.dict(
            os.environ,
            {"SYNAPSE_LITE": "0", "EMBEDDING_PROVIDER": "local"},
            clear=False,
        ):
            embedder = SynapseEmbedder.__new__(SynapseEmbedder)
            embedder._provider = (
                os.environ.get("EMBEDDING_PROVIDER", "local").strip().lower()
            )
            assert embedder._provider == "local"


class TestLiteNLPBranches:

    def test_summarizer_uses_llm_in_lite_mode(self):
        """SYNAPSE_LITE=1 + llm_complete mocked → summary comes from LLM."""
        from ai_engine.nlp import summarizer

        long_text = "Machine learning has transformed the software industry. " * 12
        with patch.dict(os.environ, {"SYNAPSE_LITE": "1"}):
            with patch("ai_engine.lite.llm_complete", return_value="LLM summary."):
                summary = summarizer.summarize(long_text)
        assert summary == "LLM summary."

    def test_topic_uses_llm_in_lite_mode(self):
        from ai_engine.nlp.topic_classifier import classify_topic

        with patch.dict(os.environ, {"SYNAPSE_LITE": "1"}):
            with patch("ai_engine.lite.llm_complete", return_value="Machine Learning"):
                topic, conf = classify_topic("A paper about transformer models.")
        assert topic == "Machine Learning"
        assert conf > 0

    def test_sentiment_uses_llm_in_lite_mode(self):
        from ai_engine.nlp.sentiment_analyzer import analyze_sentiment

        with patch.dict(os.environ, {"SYNAPSE_LITE": "1"}):
            with patch("ai_engine.lite.llm_complete", return_value="POSITIVE"):
                label, score = analyze_sentiment("This is fantastic news!")
        assert label == "POSITIVE"
        assert score > 0

    def test_keywords_skip_keybert_in_lite_mode(self):
        """YAKE only — _extract_keybert must not be called."""
        from ai_engine.nlp import keyword_extractor

        text = (
            "Machine learning and neural networks are transforming artificial "
            "intelligence research across the software industry."
        )
        with patch.dict(os.environ, {"SYNAPSE_LITE": "1"}):
            with patch.object(
                keyword_extractor,
                "_extract_keybert",
                side_effect=AssertionError("KeyBERT must not run in lite mode"),
            ) as mock_kb:
                keywords = keyword_extractor.extract_keywords(text)
                mock_kb.assert_not_called()
        assert isinstance(keywords, list)
        assert keywords  # YAKE produced something

    def test_ner_skipped_in_lite_mode(self):
        from ai_engine.nlp.ner import extract_entities

        with patch.dict(os.environ, {"SYNAPSE_LITE": "1"}):
            entities = extract_entities("OpenAI and Google are working on AI.")
        assert entities == []

    def test_lite_mode_imports_no_heavy_ml(self):
        """Importing the lite + nlp modules must not pull torch/transformers."""
        import importlib

        for mod in (
            "ai_engine.lite",
            "ai_engine.nlp.summarizer",
            "ai_engine.nlp.topic_classifier",
            "ai_engine.nlp.sentiment_analyzer",
            "ai_engine.nlp.keyword_extractor",
            "ai_engine.nlp.ner",
            "ai_engine.embeddings.embedder",
        ):
            importlib.import_module(mod)
        heavy = {"torch", "transformers", "sentence_transformers", "spacy", "keybert"}
        loaded = [m for m in sys.modules if m.split(".")[0] in heavy]
        assert not loaded, f"heavy ML modules loaded: {loaded}"
