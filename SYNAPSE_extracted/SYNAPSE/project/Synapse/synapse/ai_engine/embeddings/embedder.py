"""
ai_engine.embeddings.embedder
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Embedding generation using sentence-transformers.

Model choice (TASK-005):
  - Default: BAAI/bge-large-en-v1.5 (1024 dims) — state-of-the-art retrieval quality
  - Fallback: all-MiniLM-L6-v2 (384 dims) — faster, lower quality
  - Configurable via EMBEDDING_MODEL env var.

BGE-large query prefix:
  Queries (not documents) should be prefixed with "Represent this sentence for searching relevant passages: "
  for best retrieval performance. The embedder applies this automatically when embed_query() is called.

Batch processing defaults: 32 items per batch (configurable via env).

TASK-005 — Upgrade Embeddings to BAAI/bge-large-en-v1.5
"""

from __future__ import annotations

import logging
import os
import time
from typing import List, Optional

logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────────────────
# Default to BAAI/bge-large-en-v1.5 (1024 dims) — TASK-005
_MODEL_NAME = os.environ.get("EMBEDDING_MODEL", "BAAI/bge-large-en-v1.5")
_BATCH_SIZE = int(os.environ.get("EMBEDDING_BATCH_SIZE", "32"))
_EMBEDDING_DIM = int(os.environ.get("EMBEDDING_DIM", "1024"))

# BGE query prefix (required for best retrieval performance with BGE models)
# Only applied when embed_query() is called, NOT when embed() / embed_batch() are called.
_BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

# EMBEDDING_PROVIDER is always "local" — sentence-transformers, no API key needed.

# Singleton instance (loaded lazily)
_embedder_instance: Optional["SynapseEmbedder"] = None


class SynapseEmbedder:
    """
    Local sentence-transformers embedding engine.
    Use :func:`get_embedder` to obtain the module-level singleton.
    """

    def __init__(self) -> None:
        self._model = None
        self.dimensions: int = _EMBEDDING_DIM
        self._model_name: str = _MODEL_NAME
        self._load_model()

    # ── Model Loading ──────────────────────────────────────────────────────────

    def _load_model(self) -> None:
        """Load the embedding model (lazy, called once at startup)."""
        self._load_sentence_transformers()

    def _load_sentence_transformers(self) -> None:
        try:
            from sentence_transformers import SentenceTransformer  # noqa: PLC0415

            logger.info("Loading sentence-transformer model: %s", _MODEL_NAME)
            self._model = SentenceTransformer(_MODEL_NAME)
            self.dimensions = self._model.get_sentence_embedding_dimension()
            logger.info(
                "Sentence-transformer loaded — model=%s, dims=%d",
                _MODEL_NAME,
                self.dimensions,
            )
        except ImportError:
            logger.error(
                "sentence-transformers not installed. "
                "Run: pip install sentence-transformers"
            )
            raise

    # ── Public API ─────────────────────────────────────────────────────────────

    def embed_query(self, query: str) -> List[float]:
        """
        Generate an embedding for a search QUERY string.

        For BGE models, automatically prepends the required query prefix:
          "Represent this sentence for searching relevant passages: "

        This prefix significantly improves retrieval quality for BGE models.
        Do NOT use this prefix for documents — only for queries.

        TASK-005
        """
        if not query or not query.strip():
            return [0.0] * self.dimensions

        # Apply BGE query prefix for BGE models (use instance model_name, not module constant)
        model_name = getattr(self, "_model_name", _MODEL_NAME)
        if "bge" in model_name.lower():
            prefixed = f"{_BGE_QUERY_PREFIX}{query}"
        else:
            prefixed = query

        return self._embed_local([_truncate_text(prefixed)])[0]

    def embed(self, text: str) -> List[float]:
        """
        Generate an embedding vector for a single text string.

        Args:
            text: The input text to embed.

        Returns:
            A list of floats representing the embedding vector.
        """
        if not text or not text.strip():
            return [0.0] * self.dimensions

        text = _truncate_text(text)

        return self._embed_local([text])[0]

    def embed_batch(
        self, texts: List[str], batch_size: int = _BATCH_SIZE
    ) -> List[List[float]]:
        """
        Generate embeddings for a list of text strings in batches.

        Args:
            texts:      List of input texts.
            batch_size: Number of texts to process per batch.

        Returns:
            List of embedding vectors, one per input text.
        """
        if not texts:
            return []

        # Sanitise inputs — track original indices so we can reinsert zero vectors
        # for empty/whitespace-only strings without sending them to the model.
        # Sending empty strings produces misleading zero/near-zero vectors that
        # pollute nearest-neighbour retrieval results.
        zero_vector = [0.0] * self.dimensions
        index_map: List[int] = []  # maps clean_texts position → original index
        clean_texts: List[str] = []

        for idx, t in enumerate(texts):
            if t and t.strip():
                clean_texts.append(_truncate_text(t))
                index_map.append(idx)

        # Allocate output list, pre-filled with zero vectors for empty inputs
        results: List[List[float]] = [zero_vector[:] for _ in texts]

        if not clean_texts:
            return results

        for i in range(0, len(clean_texts), batch_size):
            batch = clean_texts[i : i + batch_size]
            batch_indices = index_map[i : i + batch_size]
            start = time.time()
            batch_embeddings = self._embed_local(batch)
            elapsed = round(time.time() - start, 2)
            logger.debug(
                "Embedded batch %d-%d in %.2fs",
                i,
                i + len(batch),
                elapsed,
            )
            for orig_idx, emb in zip(batch_indices, batch_embeddings):
                results[orig_idx] = emb

        return results

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _embed_local(self, texts: List[str]) -> List[List[float]]:
        """Embed texts using sentence-transformers (local inference)."""
        embeddings = self._model.encode(
            texts,
            convert_to_numpy=True,
            show_progress_bar=False,
            normalize_embeddings=True,
        )
        return [emb.tolist() for emb in embeddings]


# ── Utilities ──────────────────────────────────────────────────────────────────


def _truncate_text(text: str, max_chars: int = 8192) -> str:
    """Truncate text to avoid exceeding model token limits."""
    return text[:max_chars] if len(text) > max_chars else text


# ── Singleton helpers ──────────────────────────────────────────────────────────


def get_embedder() -> SynapseEmbedder:
    """Return the singleton SynapseEmbedder, loading it on first call."""
    global _embedder_instance
    if _embedder_instance is None:
        _embedder_instance = SynapseEmbedder()
    return _embedder_instance


def embed_text(text: str) -> List[float]:
    """Convenience wrapper — embed a single text string."""
    return get_embedder().embed(text)


def embed_batch(texts: List[str], batch_size: int = _BATCH_SIZE) -> List[List[float]]:
    """Convenience wrapper — embed a list of text strings in batches."""
    return get_embedder().embed_batch(texts, batch_size=batch_size)
