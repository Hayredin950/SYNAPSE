from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

# Ensure repo root on path for ai_engine import at import time
here = os.path.abspath(__file__)
repo_root = os.path.abspath(os.path.join(here, "..", "..", "..", ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)


class SummarizationPhase22Tests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse("ai-summarize")

    def test_summarize_endpoint_model_unavailable(self):
        import ai_engine.nlp.cleaner as cleaner
        import ai_engine.nlp.summarizer as summ

        with (
            patch.object(summ, "summarize", return_value=None),
            patch.object(cleaner, "clean_text", return_value="some clean text " * 20),
        ):
            resp = self.client.post(self.url, {"text": "hello world"}, format="json")
            self.assertEqual(resp.status_code, 503)
            self.assertFalse(resp.data["success"])

    def test_summarizer_respects_min_max_length(self):
        import os
        import sys

        # Ensure repo root on path for ai_engine import
        here = os.path.abspath(__file__)
        repo_root = os.path.abspath(os.path.join(here, "..", "..", "..", ".."))
        if repo_root not in sys.path:
            sys.path.insert(0, repo_root)
        import ai_engine.nlp.summarizer as summ

        fake_summary = " ".join(["token"] * 60)
        mock_pipe = MagicMock(return_value=[{"summary_text": fake_summary}])
        with patch.object(summ, "_get_summarizer", return_value=mock_pipe):
            result = summ.summarize(
                " ".join(["x"] * 200), max_length=150, min_length=50
            )
            # should return the mocked summary text unchanged
            self.assertEqual(result, fake_summary)
            # verify pipeline called with provided min/max
            mock_pipe.assert_called()
            args, kwargs = mock_pipe.call_args
            self.assertEqual(kwargs.get("max_length"), 150)
            self.assertEqual(kwargs.get("min_length"), 50)

    def test_rouge_score_nonzero_for_matching_summary(self):
        # When hypothesis equals reference, ROUGE-L F1 should be ~1.0
        try:
            from rouge_score import rouge_scorer
        except Exception:
            self.skipTest("rouge_score not installed in environment")
        reference = "OpenAI releases a new language model for research."
        hypothesis = reference
        scorer = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=True)
        scores = scorer.score(reference, hypothesis)
        self.assertIn("rougeL", scores)
        self.assertGreaterEqual(scores["rougeL"].fmeasure, 0.9)
