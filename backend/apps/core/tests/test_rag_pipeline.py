"""
Integration tests for Phase 3.1 — RAG Pipeline
Tests the chat API endpoints and RAG pipeline components with mocked Gemini/LangChain.
"""

import json
import uuid
from unittest.mock import MagicMock, PropertyMock, patch

from apps.core.models import Conversation

from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------


def _make_mock_pipeline(answer="Test answer from RAG", sources=None):
    """Return a mock RAGPipeline instance."""
    if sources is None:
        sources = [
            {
                "title": "Test Article",
                "url": "https://example.com/article",
                "content_type": "articles",
                "snippet": "This is a test snippet about the topic.",
                "similarity_score": 0.92,
            }
        ]
    mock_pipeline = MagicMock()
    mock_pipeline.chat.return_value = {
        "answer": answer,
        "sources": sources,
        "conversation_id": "test-conv-id",
    }
    mock_pipeline.get_history.return_value = [
        {"human": "What is LangChain?", "ai": "LangChain is a framework..."},
    ]
    mock_pipeline.stream_chat.return_value = iter(
        [
            "Hello",
            " world",
            "__SOURCES__:"
            + json.dumps({"sources": sources, "conversation_id": "test-conv-id"}),
        ]
    )
    mock_pipeline.delete_conversation.return_value = None
    return mock_pipeline


# ---------------------------------------------------------------------------
# Conversation Model Tests
# ---------------------------------------------------------------------------


class ConversationModelTests(TestCase):

    def test_create_conversation(self):
        conv_id = str(uuid.uuid4())
        conv = Conversation.objects.create(conversation_id=conv_id)
        self.assertEqual(conv.conversation_id, conv_id)
        self.assertEqual(conv.messages, [])
        self.assertEqual(conv.title, "")

    def test_add_message(self):
        conv = Conversation.objects.create(conversation_id=str(uuid.uuid4()))
        conv.add_message("human", "What is Python?")
        conv.add_message("ai", "Python is a programming language.")
        conv.refresh_from_db()
        self.assertEqual(len(conv.messages), 2)
        self.assertEqual(conv.messages[0]["role"], "human")
        self.assertEqual(conv.messages[0]["content"], "What is Python?")
        self.assertEqual(conv.messages[1]["role"], "ai")
        self.assertIn("ts", conv.messages[0])

    def test_get_title_from_title_field(self):
        conv = Conversation.objects.create(
            conversation_id=str(uuid.uuid4()),
            title="My custom title",
        )
        self.assertEqual(conv.get_title(), "My custom title")

    def test_get_title_from_first_human_message(self):
        conv = Conversation.objects.create(conversation_id=str(uuid.uuid4()))
        conv.add_message("human", "What is machine learning?")
        conv.add_message("ai", "Machine learning is...")
        self.assertEqual(conv.get_title(), "What is machine learning?")

    def test_get_title_fallback(self):
        conv_id = "abc-123-def"
        conv = Conversation.objects.create(conversation_id=conv_id)
        self.assertIn("abc-123", conv.get_title())

    def test_conversation_ordering(self):
        ids = [str(uuid.uuid4()) for _ in range(3)]
        for cid in ids:
            Conversation.objects.create(conversation_id=cid)
        # Most recently updated should come first
        convs = list(Conversation.objects.all())
        self.assertEqual(len(convs), 3)

    def test_unique_conversation_id(self):
        cid = str(uuid.uuid4())
        Conversation.objects.create(conversation_id=cid)
        from django.db import IntegrityError

        with self.assertRaises(IntegrityError):
            Conversation.objects.create(conversation_id=cid)


# ---------------------------------------------------------------------------
# Chat API Tests
# ---------------------------------------------------------------------------


class ChatViewTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.url = "/api/v1/ai/chat/"

    @patch("apps.core.views_chat._get_pipeline")
    def test_chat_success(self, mock_get_pipeline):
        mock_get_pipeline.return_value = _make_mock_pipeline()
        response = self.client.post(
            self.url,
            {"question": "What is LangChain?"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("answer", data)
        self.assertIn("sources", data)
        self.assertIn("conversation_id", data)
        self.assertEqual(data["answer"], "Test answer from RAG")

    @patch("apps.core.views_chat._get_pipeline")
    def test_chat_with_conversation_id(self, mock_get_pipeline):
        mock_get_pipeline.return_value = _make_mock_pipeline()
        conv_id = str(uuid.uuid4())
        response = self.client.post(
            self.url,
            {"question": "Follow-up question?", "conversation_id": conv_id},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @patch("apps.core.views_chat._get_pipeline")
    def test_chat_with_content_types_filter(self, mock_get_pipeline):
        mock_pipeline = _make_mock_pipeline()
        mock_get_pipeline.return_value = mock_pipeline
        response = self.client.post(
            self.url,
            {
                "question": "Latest ML papers?",
                "content_types": ["papers"],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Verify pipeline was called with content_types
        mock_pipeline.chat.assert_called_once()
        call_kwargs = mock_pipeline.chat.call_args[1]
        self.assertEqual(call_kwargs.get("content_types"), ["papers"])

    def test_chat_missing_question(self):
        response = self.client.post(self.url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.json())

    def test_chat_empty_question(self):
        response = self.client.post(self.url, {"question": "   "}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("apps.core.views_chat._get_pipeline")
    def test_chat_pipeline_unavailable(self, mock_get_pipeline):
        mock_get_pipeline.return_value = None
        response = self.client.post(self.url, {"question": "test"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

    @patch("apps.core.views_chat._get_pipeline")
    def test_chat_creates_conversation_in_db(self, mock_get_pipeline):
        mock_get_pipeline.return_value = _make_mock_pipeline()
        conv_id = str(uuid.uuid4())
        self.client.post(
            self.url,
            {"question": "What is RAG?", "conversation_id": conv_id},
            format="json",
        )
        # Conversation should be persisted
        self.assertTrue(Conversation.objects.filter(conversation_id=conv_id).exists())

    @patch("apps.core.views_chat._get_pipeline")
    def test_chat_pipeline_error_returns_500(self, mock_get_pipeline):
        mock_pipeline = MagicMock()
        mock_pipeline.chat.side_effect = RuntimeError("LLM error")
        mock_get_pipeline.return_value = mock_pipeline
        response = self.client.post(self.url, {"question": "test"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)


# ---------------------------------------------------------------------------
# Conversation History Tests
# ---------------------------------------------------------------------------


class ConversationHistoryViewTests(TestCase):

    def setUp(self):
        self.client = APIClient()

    def test_history_existing_conversation(self):
        conv_id = str(uuid.uuid4())
        conv = Conversation.objects.create(conversation_id=conv_id)
        conv.add_message("human", "Hello?")
        conv.add_message("ai", "Hi there!")

        url = f"/api/v1/ai/chat/{conv_id}/history/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["conversation_id"], conv_id)
        self.assertEqual(len(data["messages"]), 2)

    @patch("apps.core.views_chat._get_pipeline")
    def test_history_not_in_db_but_in_memory(self, mock_get_pipeline):
        mock_pipeline = _make_mock_pipeline()
        mock_get_pipeline.return_value = mock_pipeline
        conv_id = str(uuid.uuid4())

        url = f"/api/v1/ai/chat/{conv_id}/history/"
        response = self.client.get(url)
        # Should return from pipeline memory
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @patch("apps.core.views_chat._get_pipeline")
    def test_history_not_found(self, mock_get_pipeline):
        mock_pipeline = MagicMock()
        mock_pipeline.get_history.return_value = []
        mock_get_pipeline.return_value = mock_pipeline

        url = f"/api/v1/ai/chat/{uuid.uuid4()}/history/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


# ---------------------------------------------------------------------------
# Conversation Delete Tests
# ---------------------------------------------------------------------------


class ConversationDeleteViewTests(TestCase):

    def setUp(self):
        self.client = APIClient()

    @patch("apps.core.views_chat._get_pipeline")
    def test_delete_existing_conversation(self, mock_get_pipeline):
        mock_get_pipeline.return_value = _make_mock_pipeline()
        conv_id = str(uuid.uuid4())
        Conversation.objects.create(conversation_id=conv_id)

        url = f"/api/v1/ai/chat/{conv_id}/"
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(Conversation.objects.filter(conversation_id=conv_id).exists())

    @patch("apps.core.views_chat._get_pipeline")
    def test_delete_nonexistent_conversation(self, mock_get_pipeline):
        mock_get_pipeline.return_value = _make_mock_pipeline()
        url = f"/api/v1/ai/chat/{uuid.uuid4()}/"
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


# ---------------------------------------------------------------------------
# SSE Streaming Tests
# ---------------------------------------------------------------------------


class ChatStreamViewTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.url = "/api/v1/ai/chat/stream/"

    @patch("apps.core.views_chat._get_pipeline")
    def test_stream_returns_event_stream(self, mock_get_pipeline):
        mock_get_pipeline.return_value = _make_mock_pipeline()
        response = self.client.post(
            self.url,
            {"question": "What is RAG?"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("text/event-stream", response.get("Content-Type", ""))

    def test_stream_missing_question(self):
        response = self.client.post(self.url, {}, format="json")
        # Returns streaming response even for errors
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        content = b"".join(response.streaming_content).decode()
        self.assertIn("error", content)

    @patch("apps.core.views_chat._get_pipeline")
    def test_stream_content_contains_tokens(self, mock_get_pipeline):
        mock_get_pipeline.return_value = _make_mock_pipeline()
        response = self.client.post(
            self.url,
            {"question": "Explain transformers"},
            format="json",
        )
        content = b"".join(response.streaming_content).decode()
        self.assertIn("data:", content)


# ---------------------------------------------------------------------------
# RAG Memory Manager Unit Tests
# These tests mock langchain so they run without heavy ML deps installed.
# ---------------------------------------------------------------------------


class ConversationMemoryManagerTests(TestCase):

    def _make_mgr(self):
        """Import ConversationMemoryManager with langchain mocked."""
        import sys
        from unittest.mock import MagicMock

        # Provide stub modules for langchain deps if not installed
        stubs = {}
        for mod in [
            "langchain",
            "langchain.memory",
            "langchain_core",
            "langchain_core.messages",
            "langchain_community",
            "langchain_community.vectorstores",
        ]:
            if mod not in sys.modules:
                stubs[mod] = MagicMock()
                sys.modules[mod] = stubs[mod]

        # Stub ConversationBufferWindowMemory
        mock_mem_cls = MagicMock()
        mock_mem_instance = MagicMock()
        mock_mem_instance.chat_memory = MagicMock()
        mock_mem_instance.chat_memory.messages = []
        mock_mem_cls.return_value = mock_mem_instance
        sys.modules["langchain.memory"].ConversationBufferWindowMemory = mock_mem_cls

        # Now import (fresh)
        if "ai_engine.rag.memory" in sys.modules:
            del sys.modules["ai_engine.rag.memory"]
        from ai_engine.rag import memory as mem_module

        return mem_module.ConversationMemoryManager, stubs

    def test_new_conversation_id_is_unique(self):
        Mgr, _ = self._make_mgr()
        id1 = Mgr.new_conversation_id()
        id2 = Mgr.new_conversation_id()
        self.assertNotEqual(id1, id2)

    def test_new_conversation_id_with_user(self):
        Mgr, _ = self._make_mgr()
        cid = Mgr.new_conversation_id(user_id="user-42")
        self.assertTrue(cid.startswith("user-42:"))

    def test_memory_manager_without_redis(self):
        Mgr, _ = self._make_mgr()
        with patch("ai_engine.rag.memory._get_redis_client", return_value=None):
            mgr = Mgr()
            cid = str(uuid.uuid4())
            memory = mgr.get_or_create(cid)
            self.assertIsNotNone(memory)
            # Save turn should not raise even without Redis
            mgr.save_turn(cid, "Hello", "Hi!")
            history = mgr.get_history(cid)
            self.assertEqual(history, [])  # no Redis, no persistence

    def test_get_or_create_returns_same_instance(self):
        Mgr, _ = self._make_mgr()
        with patch("ai_engine.rag.memory._get_redis_client", return_value=None):
            mgr = Mgr()
            cid = str(uuid.uuid4())
            m1 = mgr.get_or_create(cid)
            m2 = mgr.get_or_create(cid)
            self.assertIs(m1, m2)


# ---------------------------------------------------------------------------
# RAG Pipeline Health Check
# ---------------------------------------------------------------------------


class RAGPipelineHealthTests(TestCase):

    def test_health_check_structure(self):
        """Health check should return expected structure without real LLM deps."""
        import sys
        from unittest.mock import MagicMock

        # Stub out all langchain/pgvector deps
        for mod in [
            "langchain",
            "langchain.memory",
            "langchain.chains",
            "langchain.text_splitter",
            "langchain_core",
            "langchain_core.messages",
            "langchain_core.documents",
            "langchain_core.prompts",
            "langchain_core.retrievers",
            "langchain_core.callbacks",
            "langchain_community",
            "langchain_community.vectorstores",
            "pgvector",
            "pgvector.django",
        ]:
            if mod not in sys.modules:
                sys.modules[mod] = MagicMock()

        # Clear cached pipeline modules so stubs take effect
        for mod in list(sys.modules.keys()):
            if mod.startswith("ai_engine.rag"):
                del sys.modules[mod]

        with (
            patch("ai_engine.rag.pipeline.SynapseRetriever", MagicMock()),
            patch("ai_engine.rag.pipeline.SynapseRAGChain", MagicMock()),
            patch("ai_engine.rag.pipeline.ConversationMemoryManager", MagicMock()),
        ):
            from ai_engine.rag.pipeline import RAGPipeline

            pipeline = RAGPipeline()
            health = pipeline.health_check()
            self.assertIn("status", health)
            self.assertIn("components", health)
            # LLM key reported as llm_key (value varies: gemini_configured / openrouter_configured / missing)
            self.assertIn("llm_key", health["components"])
            self.assertIn("database", health["components"])
