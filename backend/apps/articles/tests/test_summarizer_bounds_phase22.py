from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

from django.test import TestCase

FAKE_SUMMARY = " ".join(["word"] * 80)  # 80 tokens, within 50..150 bounds

# Ensure repo root on path for ai_engine import
here = os.path.abspath(__file__)
repo_root = os.path.abspath(os.path.join(here, "..", "..", "..", "..", ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)


class SummarizerBoundsTests(TestCase):
    @patch("ai_engine.nlp.summarizer._get_summarizer")
    def test_summarize_returns_within_bounds(self, mock_get):
        import ai_engine.nlp.summarizer as summ

        # Mock pipeline to return deterministic fake summary
        pipe = MagicMock(return_value=[{"summary_text": FAKE_SUMMARY}])
        mock_get.return_value = pipe

        long_text = " ".join(["token"] * 500)
        result = summ.summarize(long_text, max_length=150, min_length=50)
        self.assertIsNotNone(result)
        wc = len(result.split())
        self.assertGreaterEqual(wc, 50)
        self.assertLessEqual(wc, 150)
