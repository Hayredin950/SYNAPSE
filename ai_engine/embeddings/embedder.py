"""
ai_engine.embeddings.embedder
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Embedding generation.

Two providers, selected via EMBEDDING_PROVIDER:

  ``local`` (default) — sentence-transformers on the box.
      - Default model: BAAI/bge-large-en-v1.5 (1024 dims) — state-of-the-art
        retrieval quality (TASK-005).
      - Fallback model: all-MiniLM-L6-v2 (384 dims) — faster, lower quality.
      - Configurable via EMBEDDING_MODEL env var.

  ``api`` — NVIDIA NIM hosted embeddings via HTTPS (used by SYNAPSE Lite mode).
      - Default model: nvidia/nv-embedqa-e5-v5 (1024 dims) — verified to match
        the vector(1024) columns. No torch / sentence-transformers in RAM.
      - Configurable via EMBEDDING_API_MODEL / EMBEDDING_API_BASE_URL;
        the key defaults to NVIDIA_API_KEY.

Provider selection order:
  1. EMBEDDING_PROVIDER=api|local overrides everything.
  2. Otherwise SYNAPSE_LITE=1 defaults to "api" (small-box mode).
  3. Otherwise "local" (full mode, default).

BGE-large query prefix:
  Queries (not documents) should be prefixed with "Represent this sentence for
  searching relevant passages: " for best retrieval performance. The embedder
  applies this automatically when embed_query() is called for local BGE models.
  For the NVIDIA API provider the ``input_type=query`` parameter is used instead
  (the hosted endpoint applies the correct query prefix server-side).

Batch processing defaults: 32 items per batch (configurable via env).

TASK-005 — Upgrade Embeddings to BAAI/bge-large-en-v1.5
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
from typing import List, Optional

logger = logging.getLogger(__name__)

# ── Lite-mode provider selection ──────────────────────────────────────────────
try:
    from ai_engine.lite import is_lite_mode  # noqa: PLC0415
except ImportError:  # pragma: no cover - fallback when package root is missing

    def is_lite_mode() -> bool:
        return os.environ.get("SYNAPSE_LITE", "0").strip().lower() in (
            "1",
            "true",
            "yes",
            "on",
        )


# ── Configuration ──────────────────────────────────────────────────────────────
# Default to BAAI/bge-large-en-v1.5 (1024 dims) — TASK-005
_MODEL_NAME = os.environ.get("EMBEDDING_MODEL", "BAAI/bge-large-en-v1.5")
_BATCH_SIZE = int(os.environ.get("EMBEDDING_BATCH_SIZE", "32"))
_EMBEDDING_DIM = int(os.environ.get("EMBEDDING_DIM", "1024"))

# API provider settings (NVIDIA NIM — OpenAI-compatible /embeddings endpoint)
_API_BASE_URL = os.environ.get(
    "EMBEDDING_API_BASE_URL", "https://integrate.api.nvidia.com/v1"
).rstrip("/")
_API_MODEL = os.environ.get("EMBEDDING_API_MODEL", "nvidia/nv-embedqa-e5-v5")
_API_KEY = os.environ.get("EMBEDDING_API_KEY", "") or os.environ.get(
    "NVIDIA_API_KEY", ""
)

# Content-hash caching of embeddings. Disable with EMBEDDING_CACHE=0.
_CACHE_ENABLED = os.environ.get("EMBEDDING_CACHE", "1").lower() not in (
    "0",
    "false",
    "no",
)
_CACHE_TTL = int(os.environ.get("EMBEDDING_CACHE_TTL", str(60 * 60 * 24 * 30)))


def _get_cache():
    """
    Return Django's cache backend, or None when unavailable.

    The embedder is also imported from non-Django contexts (the FastAPI engine,
    scripts), so Django's absence must degrade to "no caching" rather than
    raising.
    """
    try:
        from django.core.cache import cache  # noqa: PLC0415

        return cache
    except Exception:
        return None


# BGE query prefix (required for best retrieval performance with BGE models)
# Only applied when embed_query() is called, NOT when embed() / embed_batch() are called.
_BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

# Singleton instance (loaded lazily)
_embedder_instance: Optional["SynapseEmbedder"] = None


class SynapseEmbedder:
    """
    Embedding engine — local sentence-transformers OR hosted API (NVIDIA NIM).

    Provider is resolved at construction time from ``EMBEDDING_PROVIDER``
    (defaulting to "api" in SYNAPSE Lite mode), so the env can be toggled
    per process. Use :func:`get_embedder` for the singleton.
    """

    def __init__(self) -> None:
        self._model = None
        self.dimensions: int = _EMBEDDING_DIM
        self._model_name: str = _MODEL_NAME
        # Resolve at construction (not import) so env toggles take effect
        # even in processes that load .env after importing this module.
        # An empty EMBEDDING_PROVIDER counts as unset (falls back to the
        # lite/full default) — otherwise `EMBEDDING_PROVIDER=` in an env file
        # would resolve to "" and skip BOTH providers.
        _raw_provider = os.environ.get("EMBEDDING_PROVIDER", "").strip().lower()
        if not _raw_provider:
            _raw_provider = "api" if is_lite_mode() else "local"
        self._provider: str = _raw_provider
        self._load_model()

    # ── Model Loading ──────────────────────────────────────────────────────────

    def _load_model(self) -> None:
        """
        Load the embedding backend (called once at construction).

        ``api`` provider loads nothing — embeddings come from the hosted
        NVIDIA NIM endpoint, so torch / sentence-transformers never enter
        memory. ``local`` loads the sentence-transformer model.
        """
        if self._provider == "api":
            if not _API_KEY:
                logger.warning(
                    "EMBEDDING_PROVIDER=api but no key set — set EMBEDDING_API_KEY "
                    "or NVIDIA_API_KEY. Embedding calls will fail until configured."
                )
            logger.info(
                "Embedder using API provider — model=%s, dims=%d (no local model)",
                _API_MODEL,
                _EMBEDDING_DIM,
            )
            self._model_name = _API_MODEL
            return
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

            # The pgvector columns are declared vector(EMBEDDING_DIM). If the
            # model emits a different width, every write fails inside Postgres
            # with an opaque cast error — and only at write time, long after
            # startup. Fail here instead, where the cause is obvious.
            if self.dimensions != _EMBEDDING_DIM:
                raise ValueError(
                    f"Embedding dimension mismatch: model {_MODEL_NAME!r} produces "
                    f"{self.dimensions}-dim vectors but the database columns are "
                    f"vector({_EMBEDDING_DIM}). Either set EMBEDDING_MODEL to a "
                    f"{_EMBEDDING_DIM}-dim model, or set EMBEDDING_DIM={self.dimensions} "
                    f"and migrate the embedding columns to match."
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

        For local BGE models, automatically prepends the required query prefix:
          "Represent this sentence for searching relevant passages: "

        This prefix significantly improves retrieval quality for BGE models.
        Do NOT use this prefix for documents — only for queries.

        For the API provider, the NVIDIA endpoint applies the query-side
        prefix server-side via ``input_type=query``.

        TASK-005
        """
        if not query or not query.strip():
            return [0.0] * self.dimensions

        # Instances created via __new__ (tests) lack _provider → default to local
        if getattr(self, "_provider", "local") == "api":
            # Go through _embed_local so identical repeated queries hit the
            # content-hash cache instead of re-billing the NVIDIA endpoint
            # (free tier is ~40 rpm). Cache key includes the input type.
            return self._embed_local([_truncate_text(query)], input_type="query")[0]

        # Apply BGE query prefix for local BGE models (use instance model_name, not module constant)
        model_name = getattr(self, "_model_name", _MODEL_NAME)
        if "bge" in model_name.lower():
            prefixed = f"{_BGE_QUERY_PREFIX}{query}"
        else:
            prefixed = query

        return self._embed_local([_truncate_text(prefixed)], input_type="passage")[0]

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

    def _cache_key(self, text: str, input_type: str = "passage") -> str:
        """Cache key for an embedding — content hash scoped to model+dims+type.

        ``input_type`` is included because the API provider embeds the same
        text differently for queries vs passages (different server-side
        prefixes); local BGE models also only prefix queries.
        """
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return f"emb:{self._model_name}:{self.dimensions}:{input_type}:{digest}"

    def _embed_local(
        self, texts: List[str], input_type: str = "passage"
    ) -> List[List[float]]:
        """
        Embed texts using the configured backend (local model OR API).

        Results are cached by content hash (scoped to input type). Scrapers
        re-process the same articles on every run, and the same story is
        often ingested from several sources, so identical text reaches this
        method repeatedly. Skipping a recompute is pure saving — for the API
        provider it also conserves the free tier's ~40 rpm quota.

        The cache is best-effort — any backend failure falls through to normal
        inference rather than breaking the caller.
        """
        if not _CACHE_ENABLED:
            return self._encode(texts, input_type=input_type)

        cache = _get_cache()
        if cache is None:
            return self._encode(texts, input_type=input_type)

        keys = [self._cache_key(t, input_type) for t in texts]
        try:
            cached = cache.get_many(keys)
        except Exception as exc:  # pragma: no cover - cache backend issues
            logger.debug("embedding cache read failed: %s", exc)
            return self._encode(texts, input_type=input_type)

        results: List[Optional[List[float]]] = [cached.get(k) for k in keys]
        missing_idx = [i for i, v in enumerate(results) if v is None]

        if missing_idx:
            fresh = self._encode([texts[i] for i in missing_idx], input_type=input_type)
            to_store = {}
            for slot, vector in zip(missing_idx, fresh):
                results[slot] = vector
                to_store[keys[slot]] = vector
            try:
                cache.set_many(to_store, timeout=_CACHE_TTL)
            except Exception as exc:  # pragma: no cover
                logger.debug("embedding cache write failed: %s", exc)

        hits = len(texts) - len(missing_idx)
        if hits:
            logger.debug("embedding cache: %d/%d hits", hits, len(texts))

        return [v for v in results if v is not None]

    def _encode(
        self, texts: List[str], input_type: str = "passage"
    ) -> List[List[float]]:
        """Run the configured backend. No caching — see _embed_local."""
        # Instances created via __new__ (tests) lack _provider → default to local
        if getattr(self, "_provider", "local") == "api":
            return self._embed_api(texts, input_type=input_type)
        embeddings = self._model.encode(
            texts,
            convert_to_numpy=True,
            show_progress_bar=False,
            normalize_embeddings=True,
        )
        return [emb.tolist() for emb in embeddings]

    def _embed_api(
        self, texts: List[str], input_type: str = "passage"
    ) -> List[List[float]]:
        """
        Embed texts via the NVIDIA NIM hosted /embeddings endpoint.

        Uses the OpenAI-compatible ``POST {base}/embeddings`` contract with
        ``input_type`` ("query" | "passage") so the server applies the right
        prompt prefix per e5-style model.

        Raises on failure so callers (embedding tasks) can retry; the cache
        layer above already degrades gracefully on backend hiccups.
        """
        import httpx  # noqa: PLC0415

        if not _API_KEY:
            raise RuntimeError(
                "EMBEDDING_PROVIDER=api but EMBEDDING_API_KEY/NVIDIA_API_KEY is not set."
            )

        resp = httpx.post(
            f"{_API_BASE_URL}/embeddings",
            headers={
                "Authorization": f"Bearer {_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": _API_MODEL,
                "input": texts,
                "input_type": input_type,
                "truncate": "END",
            },
            timeout=60.0,
        )
        resp.raise_for_status()
        data = resp.json()
        embeddings = [item["embedding"] for item in data.get("data", [])]

        # Guard: the vector columns are vector(EMBEDDING_DIM). A different
        # width means every DB write fails with an opaque cast error.
        if embeddings and len(embeddings[0]) != _EMBEDDING_DIM:
            raise ValueError(
                f"Embedding dimension mismatch: API model {_API_MODEL!r} returned "
                f"{len(embeddings[0])}-dim vectors but the database columns are "
                f"vector({_EMBEDDING_DIM})."
            )
        return embeddings


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
    return get_embedder().embed_batch(texts, batch_size=batch_size)
