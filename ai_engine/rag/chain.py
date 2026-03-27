"""
SYNAPSE RAG Chain — powered by LangChain + OpenRouter (OpenAI-compatible API).
Includes system prompt grounded in the knowledge base with source citation support.
Falls back to Google Gemini if GEMINI_API_KEY is set and OPENROUTER_API_KEY is not.
"""

import logging
import os
from typing import Any, Dict, Iterator, List, Optional

from langchain_core.documents import Document
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

from .memory import ConversationMemoryManager
from .retriever import SynapseRetriever

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_text(content: Any) -> str:
    """
    Safely extract a plain string from an LLM response's content field.

    Gemini (and some other providers) can return content as:
      - A plain string  → return as-is
      - A list of content blocks, e.g.:
          [{'type': 'text', 'text': '...'}, ...]
        or the older Anthropic-style:
          [{'type': 'text', 'text': '...', 'extras': {...}}, ...]
    In list form we concatenate all 'text' values.
    Any other type is coerced with str().
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                # 'text' key is standard across Gemini / Anthropic block formats
                parts.append(str(block.get("text", "")))
            else:
                parts.append(str(block))
        return "".join(parts)
    return str(content) if content is not None else ""


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are SYNAPSE AI, an intelligent assistant with deep knowledge \
of technology, software engineering, AI/ML research, and developer tools. \
You answer questions based on the curated knowledge base of articles, research papers, \
GitHub repositories, and videos collected by SYNAPSE.

Guidelines:
- Ground your answers in the retrieved context documents provided.
- If the context does not contain enough information, say so honestly and provide \
  general knowledge while noting it is not from the SYNAPSE knowledge base.
- Always cite the sources you used by referencing the document titles and URLs.
- Be concise, accurate, and helpful.
- Format code snippets with appropriate markdown code fences.
- When discussing research papers, mention the key findings and authors when known.

Knowledge Base Context:
{context}
"""

CONDENSE_QUESTION_PROMPT = PromptTemplate.from_template(
    """Given the following conversation history and a follow-up question, \
rephrase the follow-up question to be a standalone question that captures \
all necessary context from the conversation.

Conversation History:
{chat_history}

Follow-up Question: {question}

Standalone Question:"""
)


def _format_context_with_sources(docs: List[Document]) -> str:
    """Format retrieved documents into a numbered context block."""
    parts = []
    for i, doc in enumerate(docs, 1):
        meta = doc.metadata
        title = meta.get("title", meta.get("name", "Untitled"))
        url = meta.get("source", meta.get("url", ""))
        content_type = meta.get("content_type", "document")
        score = meta.get("similarity_score", "")
        score_str = f" (relevance: {score:.3f})" if score else ""

        header = f"[{i}] {content_type.upper()}: {title}{score_str}"
        if url:
            header += f"\n    URL: {url}"
        body = doc.page_content.strip()
        parts.append(f"{header}\n{body}")
    return "\n\n---\n\n".join(parts)


# ---------------------------------------------------------------------------
# SynapseRAGChain
# ---------------------------------------------------------------------------


class SynapseRAGChain:
    """
    Wraps LangChain's ConversationalRetrievalChain with SYNAPSE-specific:
      - System prompt grounded in the knowledge base
      - Source citation extraction
      - Streaming support
      - Conversation memory integration
    """

    def __init__(
        self,
        retriever: SynapseRetriever,
        memory_manager: ConversationMemoryManager,
        model_name: str = "gpt-3.5-turbo",
        temperature: float = 0.2,
        max_tokens: int = 1024,
        streaming: bool = False,
    ) -> None:
        self.retriever = retriever
        self.memory_manager = memory_manager
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.streaming = streaming

        self._llm = self._build_llm(
            temperature=temperature, max_tokens=max_tokens, streaming=streaming
        )

    @staticmethod
    def _build_llm(
        temperature: float = 0.2,
        max_tokens: int = 1024,
        streaming: bool = False,
        provider: str = "auto",
        model: str = "",
    ):
        """
        Build the RAG chain LLM.

        QA-24: Delegates to the shared ai_engine.agents.llm_factory.build_llm()
        to avoid duplicating provider-routing logic across the codebase.
        See llm_factory.py for the full provider selection order.
        """
        from ai_engine.agents.llm_factory import build_llm

        return build_llm(
            provider=provider,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            streaming=streaming,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def chat(
        self,
        question: str,
        conversation_id: str,
        content_types: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Process a user question and return the answer with source citations.
        Delegates to chat_with_context for a clean, dependency-free implementation.
        """
        return self.chat_with_context(
            question=question,
            conversation_id=conversation_id,
            content_types=content_types,
        )

    def chat_with_context(
        self,
        question: str,
        conversation_id: str,
        content_types: Optional[List[str]] = None,
        provider: str = "auto",
        model: str = "",
    ) -> Dict[str, Any]:
        """
        Alternative: manually retrieve docs, build prompt, and call LLM directly.
        Used for SSE streaming where we want more control.
        """
        memory = self.memory_manager.get_or_create(conversation_id)

        if content_types:
            self.retriever.content_types = content_types

        # Step 1: Retrieve docs
        docs = self.retriever.invoke(question)
        context = (
            _format_context_with_sources(docs)
            if docs
            else "No relevant documents found."
        )

        # Step 2: Condense question if there's history
        chat_history = memory.messages
        condensed_question = question
        if chat_history:
            condensed_question = self._condense_question(question, chat_history)

        # Step 3: Build final prompt
        system_content = SYSTEM_PROMPT.format(context=context)

        from langchain_core.messages import SystemMessage

        messages = [SystemMessage(content=system_content)]
        messages.extend(chat_history)
        from langchain_core.messages import HumanMessage

        messages.append(HumanMessage(content=condensed_question))

        # Step 4: Call LLM — use per-request provider/model if different from default
        llm = (
            self._build_llm(
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                provider=provider,
                model=model,
            )
            if (provider and provider != "auto") or model
            else self._llm
        )
        response = llm.invoke(messages)
        answer = (
            _extract_text(response.content)
            if hasattr(response, "content")
            else str(response)
        )

        # Persist
        self.memory_manager.save_turn(conversation_id, question, answer)

        return {
            "answer": answer,
            "sources": self._extract_sources(docs),
            "conversation_id": conversation_id,
        }

    def stream_chat(
        self,
        question: str,
        conversation_id: str,
        content_types: Optional[List[str]] = None,
        provider: str = "auto",
        model: str = "",
    ) -> Iterator[str]:
        """
        Stream chat response token-by-token via Gemini.
        Final item is a JSON-encoded metadata dict prefixed with '__SOURCES__:'.
        """
        import json

        memory = self.memory_manager.get_or_create(conversation_id)

        if content_types:
            self.retriever.content_types = content_types

        docs = self.retriever.invoke(question)
        context = (
            _format_context_with_sources(docs)
            if docs
            else "No relevant documents found."
        )

        chat_history = memory.messages
        condensed_question = question
        if chat_history:
            condensed_question = self._condense_question(question, chat_history)

        system_content = SYSTEM_PROMPT.format(context=context)

        from langchain_core.messages import HumanMessage, SystemMessage

        messages = [SystemMessage(content=system_content)]
        messages.extend(chat_history)
        messages.append(HumanMessage(content=condensed_question))

        streaming_llm = self._build_llm(
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            streaming=True,
            provider=provider,
            model=model,
        )

        full_answer = []
        for chunk in streaming_llm.stream(messages):
            token = (
                _extract_text(chunk.content)
                if hasattr(chunk, "content")
                else str(chunk)
            )
            if token:
                full_answer.append(token)
                yield token

        complete_answer = "".join(full_answer)
        self.memory_manager.save_turn(conversation_id, question, complete_answer)

        sources = self._extract_sources(docs)
        yield f"__SOURCES__:{json.dumps({'sources': sources, 'conversation_id': conversation_id})}"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _condense_question(self, question: str, chat_history: list) -> str:
        """Use Gemini to rephrase follow-up question as standalone."""
        try:
            history_str = "\n".join(
                f"{'Human' if i % 2 == 0 else 'AI'}: {m.content}"
                for i, m in enumerate(chat_history[-6:])
            )
            prompt = CONDENSE_QUESTION_PROMPT.format(
                chat_history=history_str,
                question=question,
            )
            condensed_llm = self._build_llm(temperature=0, max_tokens=256)
            result = condensed_llm.invoke(prompt)
            return (
                _extract_text(result.content)
                if hasattr(result, "content")
                else question
            )
        except Exception as exc:
            logger.warning("Question condensation failed: %s", exc)
            return question

    @staticmethod
    def _extract_sources(docs: List[Document]) -> List[Dict[str, Any]]:
        """Extract structured source info from retrieved documents."""
        sources = []
        seen_urls: set = set()
        for doc in docs:
            meta = doc.metadata
            url = meta.get("source", meta.get("url", ""))
            if url and url in seen_urls:
                continue
            if url:
                seen_urls.add(url)
            sources.append(
                {
                    "title": meta.get("title", meta.get("name", "Untitled")),
                    "url": url,
                    "content_type": meta.get("content_type", "document"),
                    "snippet": (
                        doc.page_content[:200].strip() + "..."
                        if len(doc.page_content) > 200
                        else doc.page_content.strip()
                    ),
                    "similarity_score": meta.get("similarity_score", None),
                }
            )
        return sources
