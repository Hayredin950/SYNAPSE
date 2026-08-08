"""
SYNAPSE RAG Retriever — pgvector-backed document retrieval using LangChain PGVector.

Embeddings: always sentence-transformers (local, free, no API key required).
OpenAI / langchain_openai is NOT used anywhere in this file.
"""

import logging
import os
from typing import List, Optional

from langchain_community.vectorstores import PGVector
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from pydantic import Field

from ai_engine.embeddings import get_embedder

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Connection string helper
# ---------------------------------------------------------------------------


def _build_connection_string() -> str:
    """Build PostgreSQL connection string from environment variables."""
    return (
        f"postgresql+psycopg2://"
        f"{os.environ.get('DB_USER', 'synapse_user')}:"
        f"{os.environ.get('DB_PASSWORD', 'synapse_pass')}@"
        f"{os.environ.get('DB_HOST', 'localhost')}:"
        f"{os.environ.get('DB_PORT', '5432')}/"
        f"{os.environ.get('DB_NAME', 'synapse_db')}"
    )


# ---------------------------------------------------------------------------
# LangChain-compatible embedding wrapper
# ---------------------------------------------------------------------------


class SynapseEmbeddingWrapper:
    """Wraps SynapseEmbedder so it satisfies LangChain's Embeddings interface."""

    def __init__(self) -> None:
        self._embedder = get_embedder()

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        import numpy as np

        vectors = self._embedder.embed_batch(texts)
        if isinstance(vectors, np.ndarray):
            return vectors.tolist()
        return [v.tolist() if hasattr(v, "tolist") else v for v in vectors]

    def embed_query(self, text: str) -> List[float]:
        import numpy as np

        vector = self._embedder.embed(text)
        if isinstance(vector, np.ndarray):
            return vector.tolist()
        return vector


def _get_lc_embeddings():
    """Return LangChain-compatible embedding function (always local sentence-transformers)."""
    return SynapseEmbeddingWrapper()


# ---------------------------------------------------------------------------
# PGVector collection names — one per content type
# ---------------------------------------------------------------------------

COLLECTION_NAMES = {
    "articles": "article_embeddings",
    "papers": "researchpaper_embeddings",
    "repositories": "repository_embeddings",
    "videos": "video_embeddings",
}

ALL_COLLECTIONS = list(COLLECTION_NAMES.values())


# ---------------------------------------------------------------------------
# SynapseRetriever
# ---------------------------------------------------------------------------


class SynapseRetriever(BaseRetriever):
    """
    Retrieves the most relevant SYNAPSE knowledge-base documents for a query.

    TASK-301: Now supports three retrieval modes:
      - 'semantic'  — pgvector cosine similarity only (original behaviour)
      - 'bm25'      — PostgreSQL full-text search only
      - 'hybrid'    — RRF merge of BM25 + semantic, with optional cross-encoder
                      reranking (recommended for best quality)

    Searches across all content types (articles, papers, repositories, videos).
    """

    k: int = Field(
        default=5, description="Number of documents to retrieve per collection"
    )
    score_threshold: float = Field(default=0.0, description="Minimum similarity score")
    content_types: List[str] = Field(
        default_factory=lambda: list(COLLECTION_NAMES.keys()),
        description="Content types to search",
    )
    connection_string: str = Field(default_factory=_build_connection_string)
    mode: str = Field(
        default="hybrid",
        description="Retrieval mode: 'semantic' | 'bm25' | 'hybrid'",
    )
    use_reranker: bool = Field(
        default=True,
        description="Apply cross-encoder reranking in hybrid mode",
    )

    class Config:
        arbitrary_types_allowed = True

    def _get_vectorstore(self, collection_name: str) -> PGVector:
        """Return a PGVector store for the given collection."""
        return PGVector(
            collection_name=collection_name,
            connection_string=self.connection_string,
            embedding_function=_get_lc_embeddings(),
        )

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun,
    ) -> List[Document]:
        """
        Retrieve and merge documents using the configured mode.

        Modes:
          semantic — pgvector cosine similarity (original behaviour)
          bm25     — PostgreSQL full-text search only
          hybrid   — RRF(BM25 + semantic) + optional cross-encoder rerank
        """
        if self.mode == "bm25":
            return self._bm25_retrieve(query)
        if self.mode == "hybrid":
            return self._hybrid_retrieve(query)
        # default: 'semantic'
        return self._semantic_retrieve(query)

    def _semantic_retrieve(self, query: str) -> List[Document]:
        """Original pgvector cosine-similarity retrieval."""
        all_docs: List[Document] = []

        for content_type in self.content_types:
            collection = COLLECTION_NAMES.get(content_type)
            if not collection:
                continue
            try:
                store = self._get_vectorstore(collection)
                if self.score_threshold > 0:
                    docs_with_scores = store.similarity_search_with_score(
                        query, k=self.k
                    )
                    for doc, score in docs_with_scores:
                        if score >= self.score_threshold:
                            doc.metadata["similarity_score"] = float(score)
                            doc.metadata.setdefault("content_type", content_type)
                            all_docs.append(doc)
                else:
                    docs = store.similarity_search(query, k=self.k)
                    for doc in docs:
                        doc.metadata.setdefault("content_type", content_type)
                    all_docs.extend(docs)
            except Exception as exc:
                logger.warning("Failed to retrieve from '%s': %s", collection, exc)

        seen: dict = {}
        for doc in all_docs:
            key = (
                doc.metadata.get("source")
                or doc.metadata.get("id")
                or doc.page_content[:80]
            )
            score = doc.metadata.get("similarity_score", 0.0)
            if key not in seen or score > seen[key].metadata.get(
                "similarity_score", 0.0
            ):
                seen[key] = doc

        merged = sorted(
            seen.values(),
            key=lambda d: d.metadata.get("similarity_score", 0.0),
            reverse=True,
        )
        return merged[: self.k * len(self.content_types)]

    def _bm25_retrieve(self, query: str) -> List[Document]:
        """BM25 retrieval via Django ORM (requires DB access from AI engine)."""
        docs: List[Document] = []
        try:
            import os as _os

            import django

            if not _os.environ.get("DJANGO_SETTINGS_MODULE"):
                _os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.production"
            try:
                django.setup()
            except RuntimeError:
                pass  # already set up

            from apps.core.search import bm25_search

            raw = bm25_search(query, self.content_types, self.k)

            for ct, results in raw.items():
                for r in results:
                    docs.append(
                        Document(
                            page_content=f"{r.title}\n{r.snippet}",
                            metadata={
                                "id": r.id,
                                "content_type": ct,
                                "title": r.title,
                                "bm25_rank": r.bm25_rank,
                            },
                        )
                    )
        except Exception as exc:
            logger.warning("BM25 retrieval failed: %s — falling back to semantic", exc)
            return self._semantic_retrieve(query)
        return docs

    def _hybrid_retrieve(self, query: str) -> List[Document]:
        """
        Hybrid retrieval: RRF(BM25 + semantic) with optional cross-encoder rerank.
        Falls back to semantic-only if Django ORM is unavailable.
        """
        try:
            import os as _os

            import django

            if not _os.environ.get("DJANGO_SETTINGS_MODULE"):
                _os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.production"
            try:
                django.setup()
            except RuntimeError:
                pass

            from apps.core.search import hybrid_search

            # Get query embedding from the local embedder
            embedder = _get_lc_embeddings()
            query_vector = embedder.embed_query(query)

            raw = hybrid_search(
                query=query,
                query_vector=query_vector,
                content_types=self.content_types,
                limit=self.k,
                use_reranker=self.use_reranker,
            )

            docs: List[Document] = []
            for ct, results in raw.items():
                for r in results:
                    docs.append(
                        Document(
                            page_content=f"{r.title}\n{r.snippet}",
                            metadata={
                                "id": r.id,
                                "content_type": ct,
                                "title": r.title,
                                "rrf_score": r.rrf_score,
                                "rerank_score": r.rerank_score,
                                "similarity_score": r.similarity_score,
                                "bm25_rank": r.bm25_rank,
                                "semantic_rank": r.semantic_rank,
                            },
                        )
                    )
            # Sort by final score (rerank > rrf)
            docs.sort(
                key=lambda d: d.metadata.get("rerank_score")
                or d.metadata.get("rrf_score", 0.0),
                reverse=True,
            )
            return docs

        except Exception as exc:
            logger.warning(
                "Hybrid retrieval failed: %s — falling back to semantic", exc
            )
            return self._semantic_retrieve(query)
