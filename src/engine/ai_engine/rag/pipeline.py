"""
SYNAPSE RAG Pipeline — top-level orchestrator.
Provides a singleton `RAGPipeline` that wires together the retriever,
memory manager and chain, and exposes a clean API for the Django views.
"""

import logging
import os
from functools import lru_cache
from typing import Any, Dict, Iterator, List, Optional

from .chain import SynapseRAGChain
from .memory import ConversationMemoryManager
from .retriever import SynapseRetriever

logger = logging.getLogger(__name__)


class RAGPipeline:
    """
    Top-level orchestrator for the SYNAPSE RAG pipeline.

    Usage::

        pipeline = get_rag_pipeline()
        result = pipeline.chat("What is LangChain?", conversation_id="abc-123")
        # result == {"answer": "...", "sources": [...], "conversation_id": "abc-123"}
    """

    def __init__(
        self,
        retrieval_k: int = 5,
        model_name: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> None:
        self.retrieval_k = retrieval_k
        self.model_name = model_name or os.environ.get(
            "OPENROUTER_MODEL",
            os.environ.get("GEMINI_MODEL", "google/gemini-2.0-flash-001"),
        )
        self.temperature = temperature
        self.max_tokens = max_tokens

        self.memory_manager = ConversationMemoryManager()

        self.retriever = SynapseRetriever(k=retrieval_k)

        self.chain = SynapseRAGChain(
            retriever=self.retriever,
            memory_manager=self.memory_manager,
            model_name=self.model_name,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

        logger.info(
            "RAGPipeline initialised (model=%s, k=%d)",
            self.model_name,
            self.retrieval_k,
        )

    # ------------------------------------------------------------------
    # Chat
    # ------------------------------------------------------------------

    def chat(
        self,
        question: str,
        conversation_id: str,
        content_types: Optional[List[str]] = None,
        provider: str = "auto",
        model: str = "",
    ) -> Dict[str, Any]:
        """
        Send a question through the RAG pipeline and return a structured response.

        Args:
            question:        User's question / message.
            conversation_id: Unique ID for this conversation session.
            content_types:   Optional filter — which content types to retrieve from
                             (articles, papers, repositories, videos).

        Returns::

            {
                "answer": "...",
                "sources": [{"title": ..., "url": ..., "content_type": ..., "snippet": ...}],
                "conversation_id": "...",
            }
        """
        logger.debug(
            "RAG chat — conv=%s question=%r provider=%s model=%s",
            conversation_id,
            question[:80],
            provider,
            model,
        )
        return self.chain.chat_with_context(
            question=question,
            conversation_id=conversation_id,
            content_types=content_types,
            provider=provider,
            model=model,
        )

    def stream_chat(
        self,
        question: str,
        conversation_id: str,
        content_types: Optional[List[str]] = None,
        provider: str = "auto",
        model: str = "",
    ) -> Iterator[str]:
        """
        Streaming version of chat — yields token strings.
        The final item is prefixed with ``__SOURCES__:`` and contains JSON metadata.
        TASK-302: provider/model forwarded to the RAG chain.
        """
        yield from self.chain.stream_chat(
            question=question,
            conversation_id=conversation_id,
            content_types=content_types,
            provider=provider,
            model=model,
        )

    # ------------------------------------------------------------------
    # History / Conversation management
    # ------------------------------------------------------------------

    def get_history(self, conversation_id: str) -> List[Dict[str, Any]]:
        """Return the message history for *conversation_id*."""
        return self.memory_manager.get_history(conversation_id)

    def new_conversation_id(self, user_id: Optional[str] = None) -> str:
        """Generate a new conversation ID, optionally scoped to a user."""
        return ConversationMemoryManager.new_conversation_id(user_id=user_id)

    def delete_conversation(self, conversation_id: str) -> None:
        """Delete conversation history."""
        self.memory_manager.delete_conversation(conversation_id)

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    def health_check(self) -> Dict[str, Any]:
        """Basic liveness check for the RAG pipeline components."""
        status: Dict[str, Any] = {"status": "ok", "components": {}}

        # Check Redis
        try:
            r = self.memory_manager._redis
            if r:
                r.ping()
                status["components"]["redis"] = "ok"
            else:
                status["components"]["redis"] = "unavailable (in-memory fallback)"
        except Exception as exc:
            status["components"]["redis"] = f"error: {exc}"

        # Check LLM key presence
        has_openrouter = bool(os.environ.get("OPENROUTER_API_KEY"))
        has_gemini = bool(os.environ.get("GEMINI_API_KEY"))
        if has_openrouter:
            status["components"]["llm_key"] = "openrouter_configured"
        elif has_gemini:
            status["components"]["llm_key"] = "gemini_configured"
        else:
            status["components"]["llm_key"] = "missing"
            status["status"] = "degraded"

        # Check DB connection string
        try:
            from .retriever import _build_connection_string

            conn = _build_connection_string()
            status["components"]["database"] = "connection_string_built"
        except Exception as exc:
            status["components"]["database"] = f"error: {exc}"
            status["status"] = "degraded"

        return status


# ---------------------------------------------------------------------------
# Module-level singleton (lazy, thread-safe via lru_cache)
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def get_rag_pipeline(
    retrieval_k: int = 5,
    model_name: Optional[str] = None,
    temperature: float = 0.2,
    max_tokens: int = 1024,
) -> RAGPipeline:
    """
    Return the module-level singleton RAGPipeline.
    Subsequent calls return the cached instance.
    """
    return RAGPipeline(
        retrieval_k=retrieval_k,
        model_name=model_name,
        temperature=temperature,
        max_tokens=max_tokens,
    )
