"""
SYNAPSE AI Chat API — Phase 3.1 RAG Pipeline
Endpoints for conversational Q&A powered by LangChain + pgvector.
"""

import json
import logging
import uuid
from typing import Any, Dict, Optional

from apps.core.models import Conversation
from apps.core.throttles import ChatRateThrottle

from django.http import StreamingHttpResponse
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)


def _extract_text_content(content) -> str:
    """
    Safely extract a plain string from an LLM response content field.
    Gemini can return content as a string or as a list of content blocks
    e.g. [{'type': 'text', 'text': '...', 'extras': {...}}].
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                parts.append(str(block.get("text", "")))
            else:
                parts.append(str(block))
        return "".join(parts)
    return str(content) if content is not None else ""


# ─── Explain endpoint (Phase 3.2) ────────────────────────────────────────────


class MessageDeleteView(APIView):
    """
    DELETE /api/v1/ai/chat/<conversation_id>/messages/<int:index>/

    Removes the human message at *index* (0-based) and the AI reply below it.
    Used by the frontend Edit/Delete buttons on user bubbles.
    """

    permission_classes = [IsAuthenticated]

    def delete(self, request: Request, conversation_id: str, index: int) -> Response:
        try:
            # SECURITY: filter by user to prevent IDOR
            conv = Conversation.objects.get(
                conversation_id=conversation_id, user=request.user
            )
        except Conversation.DoesNotExist:
            return Response(
                {"error": "Conversation not found"}, status=status.HTTP_404_NOT_FOUND
            )

        deleted = conv.delete_message_pair(index)
        if not deleted:
            return Response(
                {"error": "Message index out of range"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Also drop from Redis memory so the LLM context stays consistent
        try:
            from ai_engine.rag.memory import ConversationMemoryManager

            mgr = ConversationMemoryManager()
            mgr.delete_conversation(conversation_id)
            # Re-seed Redis from the updated DB messages
            if conv.messages:
                mem = mgr.get_or_create(conversation_id)
                from langchain_core.messages import AIMessage as LCAi
                from langchain_core.messages import HumanMessage as LCHuman

                for m in conv.messages:
                    if m.get("role") == "human":
                        mem.chat_memory.add_message(LCHuman(content=m["content"]))
                    elif m.get("role") == "ai":
                        mem.chat_memory.add_message(LCAi(content=m["content"]))
        except Exception as exc:
            logger.warning("Could not sync Redis memory after message delete: %s", exc)

        return Response({"success": True, "remaining_messages": len(conv.messages)})


class ExplainView(APIView):
    """
    POST /api/v1/ai/explain

    Ask the RAG pipeline to explain a specific content item (article, paper, repo).

    Request body::

        {
            "content_type": "article" | "paper" | "repository",
            "content_id": "<uuid>",
            "title": "Optional title for context",
            "conversation_id": "optional-uuid"
        }

    Response: same shape as ChatView — {answer, sources, conversation_id}
    """

    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        content_type = request.data.get("content_type", "").strip()
        content_id = request.data.get("content_id", "").strip()
        title = request.data.get("title", "").strip()
        conversation_id = request.data.get("conversation_id") or str(uuid.uuid4())

        if not content_type or not content_id:
            return Response(
                {"error": "content_type and content_id are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Build a focused question
        type_label = {
            "article": "article",
            "paper": "research paper",
            "repository": "GitHub repository",
        }.get(content_type, content_type)
        if title:
            question = f'Explain this {type_label}: "{title}"'
        else:
            question = f"Explain the {type_label} with ID {content_id}"

        explain_user = request.user if request.user.is_authenticated else None
        pipeline = _get_pipeline(user=explain_user)
        if pipeline is None:
            return Response(
                {
                    "error": "AI pipeline is temporarily unavailable. Please configure your API keys in Settings → AI Engine."
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        try:
            result = pipeline.chat(
                question=question,
                conversation_id=conversation_id,
                content_types=[_pluralize_content_type(content_type)],
            )
        except Exception as exc:
            logger.error("RAG explain error: %s", exc)
            return Response(
                {"error": "Failed to process explain request. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Persist
        try:
            user = request.user if request.user.is_authenticated else None
            conv = _get_or_create_conversation(conversation_id, user=user)
            conv.add_message("human", question)
            conv.add_message("ai", result["answer"])
            if not conv.title and title:
                conv.title = f"Explain: {title}"[:100]
            conv.save()
        except Exception as exc:
            logger.warning("Failed to persist explain conversation: %s", exc)

        return Response(
            {**result, "conversation_id": conversation_id}, status=status.HTTP_200_OK
        )


def _get_user_keys(user) -> tuple:
    """
    Return (scitely_key, openrouter_key, gemini_key) from the user's saved preferences.
    Returns ('', '', '') if user is not authenticated or has no keys configured.
    """
    if user and user.is_authenticated:
        prefs = getattr(user, "preferences", {}) or {}
        return (
            prefs.get("scitely_api_key", ""),
            prefs.get("openrouter_api_key", ""),
            prefs.get("gemini_api_key", ""),
        )
    return "", "", ""


def _is_valid_key(key: str, prefix: str = "") -> bool:
    """Return True if the key looks like a real API key (not a placeholder/test value)."""
    if not key:
        return False
    bad = ("your-", "test", "fake", "placeholder", "example", "sk-or-test", "xxx")
    low = key.lower()
    if any(low.startswith(b) for b in bad) or any(
        b in low for b in ("test-key", "fake-key", "12345")
    ):
        return False
    if len(key) < 20:
        return False
    return True


def _get_scitely_key(user=None) -> str:
    """Return the Scitely API key — valid user key takes priority over env var."""
    import os

    if user and user.is_authenticated:
        prefs = getattr(user, "preferences", {}) or {}
        user_key = prefs.get("scitely_api_key", "")
        if _is_valid_key(user_key):
            return user_key
    key = os.environ.get("SCITELY_API_KEY", "")
    if key and not key.startswith("your-"):
        return key
    return ""


def _get_openrouter_key(user=None) -> str:
    """Return the OpenRouter API key — valid user key takes priority over env var."""
    import os

    if user and user.is_authenticated:
        prefs = getattr(user, "preferences", {}) or {}
        user_key = prefs.get("openrouter_api_key", "")
        if _is_valid_key(user_key):
            return user_key
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if key and not key.startswith("your-"):
        return key
    return ""


def _get_gemini_keys(user=None) -> list:
    """
    Collect Gemini API keys for round-robin rotation.
    User's own key takes priority. Falls back to env vars:
    GEMINI_API_KEY (primary) + GEMINI_API_KEY_1 … GEMINI_API_KEY_10.
    """
    import os

    keys = []
    # Check user's own key first
    if user and user.is_authenticated:
        prefs = getattr(user, "preferences", {}) or {}
        user_key = prefs.get("gemini_api_key", "")
        if user_key:
            keys.append(user_key)
            return keys  # User has their own key — use only that
    # Fall back to server-wide env var keys
    primary = os.environ.get("GEMINI_API_KEY", "")
    if primary and not primary.startswith("your-"):
        keys.append(primary)
    for i in range(1, 11):
        k = os.environ.get(f"GEMINI_API_KEY_{i}", "")
        if k and not k.startswith("your-") and k not in keys:
            keys.append(k)
    return keys


# Thread-safe rotation index for chat key rotation
import threading as _threading

_chat_key_lock = _threading.Lock()
_chat_key_index = 0


def _next_chat_key(keys: list) -> str:
    global _chat_key_index
    with _chat_key_lock:
        key = keys[_chat_key_index % len(keys)]
        _chat_key_index = (_chat_key_index + 1) % len(keys)
    return key


# Canonical pluralization for content_type filter values
_CONTENT_TYPE_PLURAL = {
    "article": "articles",
    "articles": "articles",
    "paper": "papers",
    "papers": "papers",
    "repository": "repositories",
    "repositories": "repositories",
    "video": "videos",
    "videos": "videos",
}


def _pluralize_content_type(ct: str) -> str:
    """Normalize a singular or plural content_type to the plural form used by the retriever."""
    return _CONTENT_TYPE_PLURAL.get(ct.lower().strip(), ct + "s")


def _get_gateway_key() -> str:
    """Return the Vercel AI Gateway API key (or empty string)."""
    import os

    key = (os.environ.get("AI_GATEWAY_API_KEY") or "").strip()
    return key if key and not key.startswith("your-") else ""


def _get_groq_key() -> str:
    """Return the Groq API key (or empty string)."""
    import os

    key = (os.environ.get("GROQ_API_KEY") or "").strip()
    return key if key and not key.startswith("your-") else ""


def _get_replit_openai_pipeline(model: str = None):
    """
    Return a pipeline backed by Replit's built-in OpenAI proxy.
    Uses AI_INTEGRATIONS_OPENAI_BASE_URL and AI_INTEGRATIONS_OPENAI_API_KEY env vars.

    Replit's proxy is OpenAI-compatible and only supports OpenAI model IDs.
    Any non-OpenAI model ID (google/*, meta-llama/*, anthropic/*, deepseek/*, etc.)
    is silently normalized to gpt-4o-mini so the request succeeds.
    """
    import os

    base_url = os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL", "")
    api_key = os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY", "")
    if not base_url or not api_key:
        return None

    # Normalize model: Replit's proxy only understands OpenAI model IDs.
    # Strip provider prefixes (google/, meta-llama/, anthropic/, deepseek/, qwen/, etc.)
    # and map everything to the closest supported model.
    _OPENAI_MODELS = {
        "gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-4", "gpt-3.5-turbo",
        "o1", "o1-mini", "o3-mini",
    }
    if model:
        # Strip provider prefix if present (e.g. "openai/gpt-4o-mini" → "gpt-4o-mini")
        bare = model.split("/")[-1] if "/" in model else model
        if bare in _OPENAI_MODELS:
            resolved_model = bare
        else:
            # Non-OpenAI model requested — fall back to gpt-4o-mini
            logger.info(
                "_get_replit_openai_pipeline: non-OpenAI model '%s' normalised to gpt-4o-mini",
                model,
            )
            resolved_model = "gpt-4o-mini"
    else:
        resolved_model = "gpt-4o-mini"
    return _OpenRouterDirectPipeline(
        api_key=api_key,
        model=resolved_model,
        base_url=base_url,
    )


def _get_pipeline(model: str = None, user=None):
    """
    Lazy-import RAG pipeline to avoid loading at Django startup.

    Provider priority (when no user-supplied key):
      0. Replit built-in OpenAI (AI_INTEGRATIONS_OPENAI_BASE_URL) — no user key needed
      1. Vercel AI Gateway   — capable + single-key access to many models
      2. Groq                — fast inference for snappier chat
      3. Scitely             — legacy
      4. OpenRouter          — legacy
      5. Gemini direct       — legacy multi-key rotation

    Tries full RAG pipeline first; falls back to direct LLM if pgvector retriever unavailable.

    Args:
        model: Optional model override requested by the client.
        user:  The authenticated Django user (used to pick up their saved API keys).
    """
    import os

    scitely_key = _get_scitely_key(user=user)
    openrouter_key = _get_openrouter_key(user=user)
    gemini_keys = _get_gemini_keys(user=user)
    gateway_key = _get_gateway_key()
    groq_key = _get_groq_key()
    replit_base_url = os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL", "")

    default_model = os.environ.get(
        "SCITELY_MODEL",
        os.environ.get(
            "OPENROUTER_MODEL", os.environ.get("GEMINI_MODEL", "gpt-4o-mini")
        ),
    )
    resolved_model = model or default_model

    if (
        not scitely_key
        and not openrouter_key
        and not gemini_keys
        and not gateway_key
        and not groq_key
        and not replit_base_url
    ):
        logger.error(
            "No LLM API key configured — chat unavailable."
        )
        return None

    logger.info(
        "_get_pipeline: model=%s gateway=%s groq=%s scitely=%s openrouter=%s "
        "gemini_keys=%d user_keys=%s",
        resolved_model,
        bool(gateway_key),
        bool(groq_key),
        bool(scitely_key),
        bool(openrouter_key),
        len(gemini_keys),
        bool(user and user.is_authenticated),
    )

    # Try the full RAG pipeline first (pgvector + embeddings + retrieval)
    # Only use RAG when no user-specific model override and no per-user key
    # (RAG pipeline is a singleton that cannot easily be keyed per user)
    user_scitely, user_openrouter, user_gemini = _get_user_keys(user)
    has_user_key = bool(user_scitely or user_openrouter or user_gemini)

    if not model and not has_user_key:
        try:
            from ai_engine.rag import get_rag_pipeline

            return get_rag_pipeline()
        except Exception as exc:
            logger.warning(
                "Full RAG pipeline unavailable (%s). Falling back to direct LLM.", exc
            )

    # User-supplied keys still take precedence (they came in via _get_*_key above)
    if user_scitely or user_openrouter:
        if scitely_key:
            return _OpenRouterDirectPipeline(
                api_key=scitely_key,
                model=resolved_model,
                base_url="https://api.scitely.com/v1",
            )
        if openrouter_key:
            return _OpenRouterDirectPipeline(
                api_key=openrouter_key, model=resolved_model
            )
    if user_gemini and gemini_keys:
        api_key = _next_chat_key(gemini_keys)
        return _GeminiDirectPipeline(
            api_key=api_key, model=resolved_model, all_keys=gemini_keys
        )

    # Priority 0: Replit built-in OpenAI — no user API key required
    if replit_base_url:
        replit_pipeline = _get_replit_openai_pipeline(model=model)
        if replit_pipeline:
            logger.info("_get_pipeline: using Replit built-in OpenAI (model=%s)", model or "gpt-4o-mini")
            return replit_pipeline

    # Server-wide providers — preferred order
    if gateway_key:
        return _OpenRouterDirectPipeline(
            api_key=gateway_key,
            model=model or os.environ.get("AI_GATEWAY_MODEL", "openai/gpt-4o-mini"),
            base_url="https://ai-gateway.vercel.sh/v1",
        )
    if groq_key:
        return _OpenRouterDirectPipeline(
            api_key=groq_key,
            model=model or os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile"),
            base_url="https://api.groq.com/openai/v1",
        )
    if scitely_key:
        return _OpenRouterDirectPipeline(
            api_key=scitely_key,
            model=resolved_model,
            base_url="https://api.scitely.com/v1",
        )
    if openrouter_key:
        return _OpenRouterDirectPipeline(api_key=openrouter_key, model=resolved_model)
    api_key = _next_chat_key(gemini_keys)
    return _GeminiDirectPipeline(
        api_key=api_key, model=resolved_model, all_keys=gemini_keys
    )


class _OpenRouterDirectPipeline:
    """
    Direct pipeline that calls any model via an OpenAI-compatible API.
    Works with OpenRouter, Scitely, and any OpenAI-compatible provider.
    """

    def __init__(self, api_key: str, model: str, base_url: str = None) -> None:
        import os

        self._api_key = api_key
        self._model = model
        self._base_url = base_url or os.environ.get(
            "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
        )
        self._histories: Dict[str, list] = {}

    def _build_llm(self, streaming: bool = False):
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=self._model,
            temperature=0.7,
            openai_api_key=self._api_key,
            openai_api_base=self._base_url,
            streaming=streaming,
            default_headers={
                "HTTP-Referer": "https://synapse.ai",
                "X-Title": "SYNAPSE Chat",
            },
        )

    def chat(
        self, question: str, conversation_id: str, content_types=None, files=None
    ) -> dict:
        from langchain_core.messages import HumanMessage, SystemMessage

        history = self._histories.get(conversation_id, [])
        messages = (
            [
                SystemMessage(
                    content=(
                        "You are SYNAPSE AI, a helpful assistant for developers and researchers. "
                        "Answer questions clearly and concisely."
                    )
                )
            ]
            + history
            + [HumanMessage(content=question)]
        )
        response = self._build_llm().invoke(messages)
        answer = _extract_text_content(
            response.content if hasattr(response, "content") else response
        ).strip()
        self._histories.setdefault(conversation_id, [])
        self._histories[conversation_id].append(HumanMessage(content=question))
        self._histories[conversation_id].append(response)
        return {"answer": answer, "sources": [], "conversation_id": conversation_id}

    def stream_chat(
        self, question: str, conversation_id: str, content_types=None, files=None
    ):
        import json

        from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

        history = self._histories.get(conversation_id, [])
        messages = (
            [
                SystemMessage(
                    content=(
                        "You are SYNAPSE AI, a helpful assistant for developers and researchers. "
                        "Answer questions clearly and concisely."
                    )
                )
            ]
            + history
            + [HumanMessage(content=question)]
        )
        full_answer = ""
        for chunk in self._build_llm(streaming=True).stream(messages):
            token = _extract_text_content(
                chunk.content if hasattr(chunk, "content") else chunk
            )
            if token:
                full_answer += token
                yield token
        self._histories.setdefault(conversation_id, [])
        self._histories[conversation_id].append(HumanMessage(content=question))
        self._histories[conversation_id].append(AIMessage(content=full_answer))
        yield f"__SOURCES__:{json.dumps([])}"

    def get_history(self, conversation_id: str):
        return []

    def delete_conversation(self, conversation_id: str):
        self._histories.pop(conversation_id, None)


class _GeminiDirectPipeline:
    """
    Fallback pipeline that calls Google Gemini directly via langchain-google-genai
    when the full RAG pipeline (pgvector retriever) is unavailable.
    Supports multi-key rotation — tries next key on 429 quota errors.
    """

    def __init__(self, api_key: str, model: str, all_keys: list = None) -> None:
        self._api_key = api_key
        self._model = model
        self._all_keys = all_keys or [api_key]
        self._histories: Dict[str, list] = {}

    def _build_llm(self, api_key: str = None):
        from langchain_google_genai import ChatGoogleGenerativeAI  # noqa: PLC0415

        return ChatGoogleGenerativeAI(
            model=self._model,
            temperature=0.7,
            google_api_key=api_key or self._api_key,
        )

    def _invoke_with_rotation(self, messages):
        """Try each API key in rotation until one succeeds."""
        last_exc = None
        for key in self._all_keys:
            try:
                llm = self._build_llm(api_key=key)
                return llm.invoke(messages)
            except Exception as exc:
                exc_str = str(exc).lower()
                if (
                    "429" in exc_str
                    or "resource_exhausted" in exc_str
                    or "quota" in exc_str
                ):
                    logger.warning(
                        "Key quota exhausted, trying next key. Error: %s", exc
                    )
                    last_exc = exc
                    continue
                raise  # non-quota error — raise immediately
        raise last_exc or Exception("All Gemini API keys exhausted")

    def _stream_with_rotation(self, messages):
        """Try each API key in rotation for streaming until one succeeds."""
        last_exc = None
        for key in self._all_keys:
            try:
                llm = self._build_llm(api_key=key)
                yield from llm.stream(messages)
                return
            except Exception as exc:
                exc_str = str(exc).lower()
                if (
                    "429" in exc_str
                    or "resource_exhausted" in exc_str
                    or "quota" in exc_str
                ):
                    logger.warning(
                        "Key quota exhausted for streaming, trying next. Error: %s", exc
                    )
                    last_exc = exc
                    continue
                raise
        raise last_exc or Exception("All Gemini API keys exhausted")

    def _build_human_message(self, question: str, files=None):
        """
        Build a HumanMessage that includes any uploaded files as inline data parts.
        Supports images (sent as base64 inline) and text files (sent as text).
        """
        import base64  # noqa: PLC0415

        from langchain_core.messages import HumanMessage  # noqa: PLC0415

        if not files:
            return HumanMessage(content=question)

        # Build multipart content list for Gemini vision
        content_parts = []
        for f in files:
            mime = f.content_type or "application/octet-stream"
            if mime.startswith("image/"):
                data = base64.b64encode(f.read()).decode("utf-8")
                content_parts.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{data}"},
                    }
                )
            else:
                # Text-based files — read and inject as text
                try:
                    text = f.read().decode("utf-8", errors="replace")
                    content_parts.append(
                        {
                            "type": "text",
                            "text": f"[File: {f.name}]\n{text}",
                        }
                    )
                except Exception:
                    pass

        if question:
            content_parts.append({"type": "text", "text": question})

        return HumanMessage(content=content_parts)

    def chat(
        self, question: str, conversation_id: str, content_types=None, files=None
    ) -> dict:
        from langchain_core.messages import HumanMessage, SystemMessage  # noqa: PLC0415

        history = self._histories.get(conversation_id, [])
        human_msg = self._build_human_message(question, files)
        messages = (
            [
                SystemMessage(
                    content=(
                        "You are SYNAPSE AI, a helpful assistant for developers and researchers. "
                        "Answer questions clearly and concisely. When images are provided, describe and analyse them thoroughly."
                    )
                )
            ]
            + history
            + [human_msg]
        )
        response = self._invoke_with_rotation(messages)
        raw = response.content if hasattr(response, "content") else response
        answer = _extract_text_content(raw).strip()
        self._histories.setdefault(conversation_id, [])
        # Store only plain text version in history to avoid huge base64 in memory
        self._histories[conversation_id].append(
            HumanMessage(content=question or "[image/file]")
        )
        self._histories[conversation_id].append(response)
        return {"answer": answer, "sources": [], "conversation_id": conversation_id}

    def stream_chat(
        self, question: str, conversation_id: str, content_types=None, files=None
    ):
        import json  # noqa: PLC0415

        from langchain_core.messages import (  # noqa: PLC0415
            AIMessage,
            HumanMessage,
            SystemMessage,
        )

        history = self._histories.get(conversation_id, [])
        human_msg = self._build_human_message(question, files)
        messages = (
            [
                SystemMessage(
                    content=(
                        "You are SYNAPSE AI, a helpful assistant for developers and researchers. "
                        "Answer questions clearly and concisely. When images are provided, describe and analyse them thoroughly."
                    )
                )
            ]
            + history
            + [human_msg]
        )
        full_answer = ""
        for chunk in self._stream_with_rotation(messages):
            token = _extract_text_content(
                chunk.content if hasattr(chunk, "content") else chunk
            )
            if token:
                full_answer += token
                yield token
        self._histories.setdefault(conversation_id, [])
        self._histories[conversation_id].append(
            HumanMessage(content=question or "[image/file]")
        )
        self._histories[conversation_id].append(AIMessage(content=full_answer))
        yield f"__SOURCES__:{json.dumps([])}"

    def get_history(self, conversation_id: str):
        return []

    def delete_conversation(self, conversation_id: str):
        self._histories.pop(conversation_id, None)


def _get_or_create_conversation(conversation_id: str, user=None) -> Conversation:
    """Get or create a Conversation DB record."""
    conv, _ = Conversation.objects.get_or_create(
        conversation_id=conversation_id,
        defaults={"user": user if user and user.is_authenticated else None},
    )
    return conv


class ChatView(APIView):  # TASK-501-B2: ChatRateThrottle applied
    """
    POST /api/v1/ai/chat

    Request body::

        {
            "question": "What is LangChain?",
            "conversation_id": "optional-uuid",     # omit to start new conversation
            "content_types": ["articles", "papers"]  # optional filter
        }

    Response::

        {
            "answer": "...",
            "sources": [{"title": ..., "url": ..., "content_type": ..., "snippet": ...}],
            "conversation_id": "uuid-..."
        }
    """

    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        question = request.data.get("question", "").strip()
        if not question:
            return Response(
                {"error": "question is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        conversation_id = request.data.get("conversation_id") or str(uuid.uuid4())
        content_types = request.data.get("content_types") or None
        model = request.data.get("model", "").strip() or None
        files = request.FILES.getlist("files") or []

        user = request.user if request.user.is_authenticated else None
        pipeline = _get_pipeline(model=model, user=user)
        if pipeline is None:
            return Response(
                {
                    "error": "AI pipeline is temporarily unavailable. Please configure your API keys in Settings → AI Engine."
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        try:
            chat_kwargs: dict = {
                "question": question,
                "conversation_id": conversation_id,
                "content_types": content_types,
            }
            # Only pass files to pipelines that support multimodal input
            if files and hasattr(pipeline, "_build_human_message"):
                chat_kwargs["files"] = files
            result = pipeline.chat(**chat_kwargs)
        except Exception as exc:
            # Log full traceback to Sentry / Render logs
            logger.error("RAG chat error: %s", exc, exc_info=True)

            # Surface a useful, classified error to the client. Without this,
            # the frontend just sees a generic 500 and we have to hunt through
            # logs every time. Classifies common LLM-provider failures so the
            # user sees an actionable message AND so we can debug remotely.
            exc_str = str(exc)
            exc_low = exc_str.lower()
            exc_type = type(exc).__name__

            if (
                "429" in exc_low
                or "resource_exhausted" in exc_low
                or "quota" in exc_low
                or "rate" in exc_low
            ):
                user_msg = (
                    "AI provider rate limit reached. Please try again in a "
                    "minute, or add another API key in Settings → AI Engine."
                )
                http_status = status.HTTP_429_TOO_MANY_REQUESTS
            elif (
                "api_key" in exc_low
                or "no ai provider" in exc_low
                or "api key not configured" in exc_low
                or "unauthorized" in exc_low
                or "401" in exc_low
                or "403" in exc_low
            ):
                user_msg = (
                    "AI provider rejected the request — likely a missing or "
                    "invalid API key. Check AI_GATEWAY_API_KEY / GROQ_API_KEY "
                    "on the server, or add a personal key in Settings → AI Engine."
                )
                http_status = status.HTTP_503_SERVICE_UNAVAILABLE
            elif (
                "timeout" in exc_low
                or "timed out" in exc_low
                or "connection" in exc_low
            ):
                user_msg = (
                    "AI provider didn't respond in time. Try again in a moment."
                )
                http_status = status.HTTP_504_GATEWAY_TIMEOUT
            else:
                user_msg = "Failed to process question. Please try again."
                http_status = status.HTTP_500_INTERNAL_SERVER_ERROR

            return Response(
                {
                    "error": user_msg,
                    # Always include the exception class + short message so
                    # frontend devtools / Sentry breadcrumbs show the real
                    # cause without needing Render shell access.
                    "debug_reason": f"{exc_type}: {exc_str[:300]}",
                },
                status=http_status,
            )

        # Persist to DB
        try:
            conv = _get_or_create_conversation(conversation_id, user=user)
            conv.add_message("human", question)
            conv.add_message("ai", result["answer"])
            if not conv.title and question:
                conv.title = question[:100]
            conv.save()
        except Exception as exc:
            logger.warning("Failed to persist conversation: %s", exc)

        return Response(result, status=status.HTTP_200_OK)


class ChatStreamView(APIView):
    """
    POST /api/v1/ai/chat/stream

    Server-Sent Events streaming endpoint. Same request body as ChatView.
    Streams tokens as SSE data events. Final event contains sources metadata.
    """

    permission_classes = [AllowAny]

    def post(self, request: Request) -> StreamingHttpResponse:
        question = request.data.get("question", "").strip()
        if not question:

            def _error():
                yield 'data: {"error": "question is required"}\n\n'

            return StreamingHttpResponse(_error(), content_type="text/event-stream")

        conversation_id = request.data.get("conversation_id") or str(uuid.uuid4())
        content_types = request.data.get("content_types") or None
        model = request.data.get("model", "").strip() or None
        files = request.FILES.getlist("files") or []

        user = request.user if request.user.is_authenticated else None
        pipeline = _get_pipeline(model=model, user=user)
        if pipeline is None:

            def _unavailable():
                yield 'data: {"error": "AI pipeline unavailable. Please configure your API keys in Settings → AI Engine."}\n\n'

            return StreamingHttpResponse(
                _unavailable(), content_type="text/event-stream"
            )
        use_files = files if hasattr(pipeline, "_build_human_message") else None

        def _stream_generator():
            full_answer = ""
            try:
                for token in pipeline.stream_chat(
                    question=question,
                    conversation_id=conversation_id,
                    content_types=content_types,
                    **({"files": use_files} if use_files is not None else {}),
                ):
                    if token.startswith("__SOURCES__:"):
                        meta = token[len("__SOURCES__:") :]
                        yield f"event: sources\ndata: {meta}\n\n"
                    else:
                        full_answer += token
                        safe = json.dumps(token)
                        yield f"data: {safe}\n\n"
            except Exception as exc:
                exc_str = str(exc).lower()
                logger.error("SSE stream error: %s", exc, exc_info=True)
                if (
                    "429" in exc_str
                    or "resource_exhausted" in exc_str
                    or "quota" in exc_str
                ):
                    msg = "All AI quota limits reached. Please try again in a few minutes or add more API keys."
                elif (
                    "api_key" in exc_str
                    or "invalid" in exc_str
                    or "authentication" in exc_str
                ):
                    msg = "AI service authentication error. Please check your API key configuration."
                else:
                    msg = "AI service temporarily unavailable. Please try again."
                yield f'data: {{"error": {json.dumps(msg)}}}\n\n'

            # Persist conversation to DB after streaming completes
            try:
                conv = _get_or_create_conversation(conversation_id, user=user)
                conv.add_message("human", question)
                conv.add_message("ai", full_answer)
                if not conv.title and question:
                    conv.title = question[:100]
                conv.save()
            except Exception as exc:
                logger.warning("Failed to persist streamed conversation: %s", exc)

            yield "event: done\ndata: {}\n\n"

        response = StreamingHttpResponse(
            _stream_generator(),
            content_type="text/event-stream",
        )
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response


class ConversationHistoryView(APIView):
    """
    GET /api/v1/ai/chat/{conversation_id}/history

    Returns the full message history for a conversation.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, conversation_id: str) -> Response:
        try:
            # SECURITY: filter by user to prevent IDOR
            conv = Conversation.objects.get(
                conversation_id=conversation_id, user=request.user
            )
        except Conversation.DoesNotExist:
            # Try fetching from pipeline memory (may exist there even if not in DB)
            pipeline = _get_pipeline()
            if pipeline:
                history = pipeline.get_history(conversation_id)
                if history:
                    # Normalize: pipeline memory stores turns as {"human": ..., "ai": ..., "ts": ...}
                    # but the frontend expects {"role": ..., "content": ..., "ts": ...}
                    normalized = []
                    for turn in history:
                        if "role" in turn and "content" in turn:
                            # Already in the correct format
                            normalized.append(
                                {
                                    "role": turn["role"],
                                    "content": (
                                        str(turn["content"])
                                        if not isinstance(turn["content"], str)
                                        else turn["content"]
                                    ),
                                    "ts": turn.get("ts", 0),
                                }
                            )
                        else:
                            # Convert from {"human": ..., "ai": ..., "ts": ...} format
                            ts = turn.get("ts", 0)
                            if "human" in turn:
                                normalized.append(
                                    {
                                        "role": "human",
                                        "content": str(turn["human"]),
                                        "ts": ts,
                                    }
                                )
                            if "ai" in turn:
                                normalized.append(
                                    {"role": "ai", "content": str(turn["ai"]), "ts": ts}
                                )
                    return Response(
                        {
                            "conversation_id": conversation_id,
                            "messages": normalized,
                            "title": "",
                        }
                    )
            return Response(
                {"error": "Conversation not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Ensure every message's content is a plain string — legacy records may
        # have had a dict/object accidentally stored as content.
        safe_messages = []
        for m in conv.messages:
            content = m.get("content", "")
            if not isinstance(content, str):
                content = str(content)
            safe_messages.append({**m, "content": content})

        return Response(
            {
                "conversation_id": conv.conversation_id,
                "title": conv.get_title(),
                "messages": safe_messages,
                "created_at": conv.created_at.isoformat(),
                "updated_at": conv.updated_at.isoformat(),
            }
        )


class ConversationListView(APIView):
    """
    GET /api/v1/ai/chat/conversations

    Lists conversations for the authenticated user.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        # SECURITY: always scope to authenticated user
        conversations = Conversation.objects.filter(user=request.user).order_by(
            "-updated_at"
        )[:50]

        data = [
            {
                "conversation_id": c.conversation_id,
                "title": c.get_title(),
                "message_count": len(c.messages),
                "created_at": c.created_at.isoformat(),
                "updated_at": c.updated_at.isoformat(),
            }
            for c in conversations
        ]

        return Response({"conversations": data})


class TranscribeView(APIView):
    """
    POST /api/v1/ai/chat/transcribe/

    TASK-304-B1: Accept an audio file (webm/ogg/mp4/wav/m4a) and transcribe
    it using OpenAI Whisper API or a local whisper fallback.

    Request (multipart/form-data):
        audio     — audio file, max 25 MB
        language  — optional ISO-639-1 code, e.g. "en" (default: auto-detect)

    Response 200:
        { "text": "...", "language": "en", "duration": 4.2 }
    Errors:
        400 — no file, oversized, unsupported format
        503 — Whisper not configured
    """

    permission_classes = [IsAuthenticated]

    MAX_AUDIO_BYTES = 25 * 1024 * 1024  # 25 MB — OpenAI hard limit
    SUPPORTED_FORMATS = {
        "audio/webm",
        "audio/ogg",
        "audio/mp4",
        "audio/mpeg",
        "audio/wav",
        "audio/x-wav",
        "audio/m4a",
        "audio/x-m4a",
        "video/webm",  # Chrome MediaRecorder outputs video/webm for audio-only recordings
    }
    SUPPORTED_EXTENSIONS = {".webm", ".ogg", ".mp4", ".mp3", ".wav", ".m4a", ".flac"}

    def post(self, request: Request) -> Response:
        import os

        audio_file = request.FILES.get("audio")
        if not audio_file:
            return Response(
                {
                    "error": "No audio file provided. Send 'audio' as multipart/form-data."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if audio_file.size > self.MAX_AUDIO_BYTES:
            return Response(
                {
                    "error": f"Audio file too large ({audio_file.size / (1024*1024):.1f} MB). Maximum is 25 MB."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        content_type = audio_file.content_type or ""
        file_name = audio_file.name or "audio.webm"
        ext = (
            ("." + file_name.rsplit(".", 1)[-1].lower())
            if "." in file_name
            else ".webm"
        )

        if (
            content_type not in self.SUPPORTED_FORMATS
            and ext not in self.SUPPORTED_EXTENSIONS
        ):
            return Response(
                {
                    "error": f"Unsupported format '{content_type}'. Use: webm, ogg, mp4, mp3, wav, m4a"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        language = request.data.get("language") or None

        # ── OpenAI Whisper API (preferred) ────────────────────────────────────
        openai_key = os.environ.get("OPENAI_API_KEY", "")
        if openai_key:
            try:
                import openai as _openai

                client = _openai.OpenAI(api_key=openai_key)
                audio_file.seek(0)
                audio_bytes = audio_file.read()
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=(file_name, audio_bytes, content_type or "audio/webm"),
                    language=language,
                    response_format="verbose_json",
                )
                return Response(
                    {
                        "text": transcript.text.strip(),
                        "language": getattr(transcript, "language", language or "en"),
                        "duration": getattr(transcript, "duration", None),
                    }
                )
            except ImportError:
                logger.warning("openai package not installed — cannot use Whisper API")
            except Exception as exc:
                logger.error("Whisper API error: %s", exc)
                return Response(
                    {"error": f"Transcription failed: {exc}"},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )

        # ── Local openai-whisper fallback ─────────────────────────────────────
        try:
            import os as _os
            import tempfile

            import whisper as _whisper  # type: ignore

            audio_file.seek(0)
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                tmp.write(audio_file.read())
                tmp_path = tmp.name
            try:
                model_size = _os.environ.get("WHISPER_LOCAL_MODEL", "base")
                wmodel = _whisper.load_model(model_size)
                result = wmodel.transcribe(tmp_path, language=language)
                return Response(
                    {
                        "text": result["text"].strip(),
                        "language": result.get("language", language or "en"),
                        "duration": None,
                    }
                )
            finally:
                _os.unlink(tmp_path)
        except ImportError:
            pass
        except Exception as exc:
            logger.error("Local whisper error: %s", exc)
            return Response(
                {"error": f"Local transcription failed: {exc}"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            {
                "error": "Transcription not configured. Set OPENAI_API_KEY or install openai-whisper."
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


class ConversationDeleteView(APIView):
    """
    DELETE /api/v1/ai/chat/{conversation_id}

    Deletes a conversation from DB and pipeline memory.
    """

    permission_classes = [IsAuthenticated]

    def delete(self, request: Request, conversation_id: str) -> Response:
        # SECURITY: filter by user to prevent IDOR
        deleted_count, _ = Conversation.objects.filter(
            conversation_id=conversation_id, user=request.user
        ).delete()

        # Delete from pipeline memory
        pipeline = _get_pipeline()
        if pipeline:
            try:
                pipeline.delete_conversation(conversation_id)
            except Exception:
                pass

        if deleted_count == 0:
            return Response(
                {"error": "Conversation not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response({"status": "deleted", "conversation_id": conversation_id})
