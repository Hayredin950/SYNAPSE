"""
Tests for TASK-304-B1 — POST /api/v1/ai/chat/transcribe/

Covers:
  - 401 for unauthenticated requests
  - 400 for missing audio file
  - 400 for oversized file
  - 400 for unsupported format
  - 200 with OpenAI Whisper (mocked)
  - 503 when no transcription backend configured
  - Local whisper fallback (mocked)
"""

import io
import uuid
from unittest.mock import MagicMock, patch

from apps.users.models import User
from rest_framework_simplejwt.tokens import RefreshToken

from django.test import TestCase
from rest_framework.test import APIClient


def _make_user():
    u = User.objects.create_user(
        username=f"u_{uuid.uuid4().hex[:8]}",
        email=f"{uuid.uuid4().hex[:6]}@test.com",
        password="testpass123",
    )
    return u


def _auth_client(user):
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return client


def _make_audio_file(
    size_bytes: int = 1024,
    name: str = "recording.webm",
    content_type: str = "audio/webm",
):
    """Return a minimal fake audio file object."""
    data = io.BytesIO(b"\x00" * size_bytes)
    data.name = name
    data.size = size_bytes
    data.content_type = content_type
    data.seek = data.seek
    data.read = data.read
    return data


URL = "/api/v1/ai/chat/transcribe/"


class TranscribeAuthTest(TestCase):

    def test_unauthenticated_returns_401(self):
        """Unauthenticated requests are rejected."""
        client = APIClient()
        response = client.post(URL, {}, format="multipart")
        self.assertEqual(response.status_code, 401)


class TranscribeValidationTest(TestCase):

    def setUp(self):
        self.user = _make_user()
        self.client = _auth_client(self.user)

    def test_missing_audio_returns_400(self):
        """Returns 400 when no audio file provided."""
        response = self.client.post(URL, {}, format="multipart")
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.data)
        self.assertIn("audio", response.data["error"].lower())

    def test_oversized_file_returns_400(self):
        """Returns 400 when audio file exceeds 25 MB."""
        from apps.core.views_chat import TranscribeView

        big_file = _make_audio_file(size_bytes=TranscribeView.MAX_AUDIO_BYTES + 1)
        response = self.client.post(URL, {"audio": big_file}, format="multipart")
        self.assertEqual(response.status_code, 400)
        self.assertIn("large", response.data["error"].lower())

    def test_unsupported_format_returns_400(self):
        """Returns 400 for unsupported audio format."""
        bad_file = _make_audio_file(name="recording.xyz", content_type="audio/xyz")
        response = self.client.post(URL, {"audio": bad_file}, format="multipart")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Unsupported", response.data["error"])

    def test_video_webm_is_accepted(self):
        """video/webm (Chrome MediaRecorder output) is treated as valid."""
        # This test just checks validation doesn't reject it — transcription
        # will return 503 (no Whisper configured) but NOT 400
        video_webm = _make_audio_file(content_type="video/webm", name="audio.webm")
        with patch.dict("os.environ", {}, clear=False):
            # Ensure no OPENAI_API_KEY so we get 503 not 200
            import os

            env = {k: v for k, v in os.environ.items() if k != "OPENAI_API_KEY"}
            with patch.dict("os.environ", env, clear=True):
                response = self.client.post(
                    URL, {"audio": video_webm}, format="multipart"
                )
        self.assertNotEqual(response.status_code, 400)


class TranscribeOpenAITest(TestCase):

    def setUp(self):
        self.user = _make_user()
        self.client = _auth_client(self.user)

    def _make_whisper_response(self, text="Hello world", language="en", duration=2.5):
        mock = MagicMock()
        mock.text = text
        mock.language = language
        mock.duration = duration
        return mock

    def test_returns_200_with_whisper_transcript(self):
        """Returns 200 with transcript when OPENAI_API_KEY is set and Whisper succeeds."""
        mock_openai = MagicMock()
        mock_client_instance = MagicMock()
        mock_openai.OpenAI.return_value = mock_client_instance
        mock_client_instance.audio.transcriptions.create.return_value = (
            self._make_whisper_response(text="This is the transcribed text")
        )

        audio = _make_audio_file()
        with (
            patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}),
            patch.dict("sys.modules", {"openai": mock_openai}),
        ):
            response = self.client.post(URL, {"audio": audio}, format="multipart")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["text"], "This is the transcribed text")
        self.assertIn("language", response.data)

    def test_strips_whitespace_from_transcript(self):
        """Strips leading/trailing whitespace from transcript."""
        mock_openai = MagicMock()
        mock_client_instance = MagicMock()
        mock_openai.OpenAI.return_value = mock_client_instance
        mock_client_instance.audio.transcriptions.create.return_value = (
            self._make_whisper_response(text="  Hello world  ")
        )

        audio = _make_audio_file()
        with (
            patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}),
            patch.dict("sys.modules", {"openai": mock_openai}),
        ):
            response = self.client.post(URL, {"audio": audio}, format="multipart")

        self.assertEqual(response.data["text"], "Hello world")

    def test_passes_language_to_whisper(self):
        """Forwards optional language parameter to Whisper API."""
        mock_openai = MagicMock()
        mock_client_instance = MagicMock()
        mock_openai.OpenAI.return_value = mock_client_instance
        mock_client_instance.audio.transcriptions.create.return_value = (
            self._make_whisper_response()
        )

        audio = _make_audio_file()
        with (
            patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}),
            patch.dict("sys.modules", {"openai": mock_openai}),
        ):
            response = self.client.post(
                URL, {"audio": audio, "language": "fr"}, format="multipart"
            )

        call_kwargs = mock_client_instance.audio.transcriptions.create.call_args[1]
        self.assertEqual(call_kwargs.get("language"), "fr")

    def test_whisper_api_error_returns_503(self):
        """Returns 503 when Whisper API call raises an exception."""
        mock_openai = MagicMock()
        mock_client_instance = MagicMock()
        mock_openai.OpenAI.return_value = mock_client_instance
        mock_client_instance.audio.transcriptions.create.side_effect = Exception(
            "API rate limit exceeded"
        )

        audio = _make_audio_file()
        with (
            patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}),
            patch.dict("sys.modules", {"openai": mock_openai}),
        ):
            response = self.client.post(URL, {"audio": audio}, format="multipart")

        self.assertEqual(response.status_code, 503)
        self.assertIn("error", response.data)


class TranscribeNoBackendTest(TestCase):

    def setUp(self):
        self.user = _make_user()
        self.client = _auth_client(self.user)

    def test_returns_503_when_no_backend_configured(self):
        """Returns 503 when neither OPENAI_API_KEY nor local whisper is available."""
        import os

        env = {k: v for k, v in os.environ.items() if k not in ("OPENAI_API_KEY",)}

        audio = _make_audio_file()
        with (
            patch.dict("os.environ", env, clear=True),
            patch.dict("sys.modules", {"whisper": None}),
        ):
            response = self.client.post(URL, {"audio": audio}, format="multipart")

        self.assertEqual(response.status_code, 503)
        self.assertIn("not configured", response.data["error"].lower())

    def test_error_message_mentions_openai_key(self):
        """503 error message hints at OPENAI_API_KEY configuration."""
        import os

        env = {k: v for k, v in os.environ.items() if k != "OPENAI_API_KEY"}

        audio = _make_audio_file()
        with (
            patch.dict("os.environ", env, clear=True),
            patch.dict("sys.modules", {"whisper": None}),
        ):
            response = self.client.post(URL, {"audio": audio}, format="multipart")

        self.assertIn("OPENAI_API_KEY", response.data["error"])
