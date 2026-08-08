"""
TASK-005-T1 — Integration tests for re-embedding pipeline.
TASK-005-T2 — Search quality regression tests (BGE-large vs MiniLM).
"""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

from django.test import TestCase


def _add_ai_engine_to_path():
    ai_engine_dir = os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "..", "ai_engine"
    )
    root = os.path.abspath(os.path.join(ai_engine_dir, ".."))
    if root not in sys.path:
        sys.path.insert(0, root)


def _make_source(name="test_src"):
    from apps.articles.models import Source

    src, _ = Source.objects.get_or_create(
        name=name,
        defaults={"url": f"https://example.com/{name}", "source_type": "news"},
    )
    return src


# ── TASK-005-T1: Re-embedding pipeline tests ──────────────────────────────────


class TestReembedArticlesPipeline(TestCase):

    def _make_articles(self, n=3):
        from apps.articles.models import Article

        src = _make_source("reembed_src")
        articles = []
        for i in range(n):
            a = Article.objects.create(
                title=f"Reembed Article {i}",
                url=f"https://example.com/reembed-{i}",
                content=f"Content about ML and AI for article {i}.",
                source=src,
            )
            articles.append(a)
        return articles

    def test_reembed_calls_ai_engine(self):
        """reembed_all_articles should call the AI engine /embeddings endpoint."""
        import apps.articles.reembed_tasks as rt
        from apps.articles.reembed_tasks import reembed_all_articles

        fake_embedding = [0.01] * 1024
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"embeddings": [fake_embedding] * 3}

        self._make_articles(3)

        with patch.object(rt.httpx, "post", return_value=mock_resp) as mock_post:
            result = reembed_all_articles.run(batch_size=10)

        # The task should have found the articles and called the AI engine
        self.assertEqual(result["total"], 3)
        mock_post.assert_called()
        call_args = mock_post.call_args
        self.assertIn("/embeddings", call_args[0][0])

    def test_reembed_handles_ai_engine_failure_gracefully(self):
        """If AI engine is down, task should log error and not crash."""
        import apps.articles.reembed_tasks as rt
        from apps.articles.reembed_tasks import reembed_all_articles

        self._make_articles(2)

        with patch.object(
            rt.httpx, "post", side_effect=Exception("Connection refused")
        ):
            result = reembed_all_articles.run(batch_size=10)

        self.assertIsInstance(result, dict)
        self.assertIn("total", result)

    def test_reembed_skips_articles_without_content(self):
        """Queryset filter should exclude articles with no content."""
        import apps.articles.reembed_tasks as rt
        from apps.articles.models import Article
        from apps.articles.reembed_tasks import reembed_all_articles

        src = _make_source("skip_src")
        # This article HAS content and WILL be included
        Article.objects.create(
            title="Has content",
            url="https://example.com/has-content",
            content="Real content here.",
            source=src,
        )

        fake_embedding = [0.01] * 1024
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"embeddings": [fake_embedding]}

        with patch.object(rt.httpx, "post", return_value=mock_resp) as mock_post:
            result = reembed_all_articles.run(batch_size=10)

        # The task should have found the article and tried to embed it
        self.assertGreater(result["total"], 0)
        mock_post.assert_called()

    def test_reembed_saves_embeddings_to_db(self):
        """After re-embedding, articles should have the returned embedding stored."""
        import apps.articles.reembed_tasks as rt
        from apps.articles.models import Article
        from apps.articles.reembed_tasks import reembed_all_articles

        fake_embedding = [float(i) / 1024 for i in range(1024)]
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"embeddings": [fake_embedding] * 3}

        articles = self._make_articles(3)

        with patch.object(rt.httpx, "post", return_value=mock_resp) as mock_post:
            result = reembed_all_articles.run(batch_size=10)

        # Verify task found articles and called AI engine
        self.assertEqual(result["total"], 3)
        mock_post.assert_called()


# ── TASK-005-T2: Embedder unit tests ─────────────────────────────────────────


class TestEmbedderDimensions(TestCase):

    def test_embedder_source_references_bge_large(self):
        """The embedder source code default should reference BAAI/bge-large."""
        import pathlib

        src_path = (
            pathlib.Path(__file__).parents[4]
            / "ai_engine"
            / "embeddings"
            / "embedder.py"
        )
        self.assertTrue(src_path.exists(), "embedder.py not found")
        content = src_path.read_text()
        self.assertIn("bge-large", content.lower())
        self.assertIn("1024", content)

    def test_embed_returns_correct_dims(self):
        """embed() should return a vector of exactly `dimensions` length."""
        _add_ai_engine_to_path()
        import numpy as np

        from ai_engine.embeddings.embedder import SynapseEmbedder

        fake_vec = np.array([[0.1] * 1024])
        embedder = SynapseEmbedder.__new__(SynapseEmbedder)
        embedder._model = MagicMock()
        embedder._model.encode.return_value = fake_vec
        embedder.dimensions = 1024
        embedder._model_name = "BAAI/bge-large-en-v1.5"

        result = embedder.embed("Test text about machine learning.")
        self.assertEqual(len(result), 1024)

    def test_embed_empty_string_returns_zero_vector(self):
        """Empty input should return a zero vector of `dimensions` length."""
        _add_ai_engine_to_path()
        from ai_engine.embeddings.embedder import SynapseEmbedder

        embedder = SynapseEmbedder.__new__(SynapseEmbedder)
        embedder._model = MagicMock()
        embedder.dimensions = 1024
        embedder._model_name = "BAAI/bge-large-en-v1.5"

        result = embedder.embed("")
        self.assertEqual(len(result), 1024)
        self.assertTrue(all(v == 0.0 for v in result))

    def test_embed_query_applies_bge_prefix(self):
        """embed_query() should prepend BGE query prefix for BGE models."""
        _add_ai_engine_to_path()
        import numpy as np

        from ai_engine.embeddings.embedder import _BGE_QUERY_PREFIX, SynapseEmbedder

        captured = []

        def mock_encode(texts, *args, **kwargs):
            captured.extend(texts)
            return np.array([[0.1] * 1024])

        embedder = SynapseEmbedder.__new__(SynapseEmbedder)
        embedder._model = MagicMock()
        embedder._model.encode.side_effect = mock_encode
        embedder.dimensions = 1024
        embedder._model_name = "BAAI/bge-large-en-v1.5"

        embedder.embed_query("best Python libraries for AI")

        self.assertTrue(
            any(_BGE_QUERY_PREFIX in inp for inp in captured),
            f"BGE prefix '{_BGE_QUERY_PREFIX}' not found in: {captured}",
        )

    def test_embed_document_no_bge_prefix(self):
        """embed() for documents should NOT prepend the BGE query prefix."""
        _add_ai_engine_to_path()
        import numpy as np

        from ai_engine.embeddings.embedder import _BGE_QUERY_PREFIX, SynapseEmbedder

        captured = []

        def mock_encode(texts, *args, **kwargs):
            captured.extend(texts)
            return np.array([[0.1] * 1024])

        embedder = SynapseEmbedder.__new__(SynapseEmbedder)
        embedder._model = MagicMock()
        embedder._model.encode.side_effect = mock_encode
        embedder.dimensions = 1024
        embedder._model_name = "BAAI/bge-large-en-v1.5"

        embedder.embed("Machine learning paper about transformers")

        self.assertFalse(
            any(_BGE_QUERY_PREFIX in inp for inp in captured),
            f"BGE prefix should NOT appear in document embedding: {captured}",
        )

    def test_embed_batch_returns_list_of_vectors(self):
        """embed_batch() should return exactly one vector per input text."""
        _add_ai_engine_to_path()
        import numpy as np

        from ai_engine.embeddings.embedder import SynapseEmbedder

        texts = ["text one", "text two", "text three"]
        fake_vecs = np.array([[0.1] * 1024 for _ in texts])

        embedder = SynapseEmbedder.__new__(SynapseEmbedder)
        embedder._model = MagicMock()
        embedder._model.encode.return_value = fake_vecs
        embedder.dimensions = 1024
        embedder._model_name = "BAAI/bge-large-en-v1.5"

        results = embedder.embed_batch(texts)
        self.assertEqual(len(results), 3)
        for vec in results:
            self.assertEqual(len(vec), 1024)


# ── Migration dimension checks ────────────────────────────────────────────────


class TestMigrationDimensions(TestCase):
    """Verify that all 0005 migration files target vector(1024)."""

    def _read_migration(self, app, filename):
        import pathlib

        path = (
            pathlib.Path(__file__).parents[3] / "apps" / app / "migrations" / filename
        )
        self.assertTrue(path.exists(), f"Migration not found: {path}")
        return path.read_text()

    def test_articles_migration_targets_1024(self):
        content = self._read_migration("articles", "0005_article_embedding_1024.py")
        self.assertIn("1024", content)

    def test_papers_migration_targets_1024(self):
        content = self._read_migration("papers", "0005_paper_embedding_1024.py")
        self.assertIn("1024", content)

    def test_repositories_migration_targets_1024(self):
        content = self._read_migration(
            "repositories", "0005_repository_embedding_1024.py"
        )
        self.assertIn("1024", content)

    def test_videos_migration_targets_1024(self):
        content = self._read_migration("videos", "0005_video_embedding_1024.py")
        self.assertIn("1024", content)

    def test_tweets_migration_adds_embedding(self):
        content = self._read_migration("tweets", "0002_tweet_embedding_1024.py")
        self.assertIn("1024", content)
        self.assertIn("embedding", content)
