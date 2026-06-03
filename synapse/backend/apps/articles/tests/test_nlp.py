"""
Unit tests for Phase 2.1 — NLP Processing Pipeline.

Tests cover each NLP module independently using mocks so that heavy
ML dependencies (transformers, spaCy, KeyBERT) are not required at
test-run time.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Ensure ai_engine is importable
PROJECT_ROOT = os.path.dirname(
    os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    )
)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# ── Cleaner tests ─────────────────────────────────────────────────────────────


class TestCleaner(unittest.TestCase):

    def setUp(self):
        from ai_engine.nlp.cleaner import (
            clean_html,
            clean_text,
            normalize_unicode,
            normalize_whitespace,
        )

        self.clean_html = clean_html
        self.normalize_whitespace = normalize_whitespace
        self.normalize_unicode = normalize_unicode
        self.clean_text = clean_text

    def test_clean_html_strips_tags(self):
        html = "<p>Hello <b>World</b></p>"
        result = self.clean_html(html)
        self.assertNotIn("<p>", result)
        self.assertIn("Hello", result)
        self.assertIn("World", result)

    def test_clean_html_removes_scripts(self):
        html = "<html><script>alert('xss')</script><p>Content</p></html>"
        result = self.clean_html(html)
        self.assertNotIn("alert", result)
        self.assertIn("Content", result)

    def test_clean_html_empty_string(self):
        self.assertEqual(self.clean_html(""), "")

    def test_clean_html_plain_text_passthrough(self):
        plain = "Hello World"
        result = self.clean_html(plain)
        self.assertIn("Hello", result)

    def test_normalize_whitespace_collapses_spaces(self):
        text = "hello   world   foo"
        result = self.normalize_whitespace(text)
        self.assertEqual(result, "hello world foo")

    def test_normalize_whitespace_strips_edges(self):
        result = self.normalize_whitespace("   hello   ")
        self.assertEqual(result, "hello")

    def test_normalize_whitespace_collapses_newlines(self):
        text = "line1\n\n\n\nline2"
        result = self.normalize_whitespace(text)
        self.assertNotIn("\n\n\n", result)

    def test_normalize_unicode_nfkc(self):
        # Ligature fi should be normalised
        text = "\ufb01le"  # 'fi' ligature + 'le'
        result = self.normalize_unicode(text)
        self.assertEqual(result, "file")

    def test_clean_text_full_pipeline(self):
        html = "<h1>AI News</h1><p>OpenAI released  GPT-5.</p><script>bad()</script>"
        result = self.clean_text(html)
        self.assertNotIn("<h1>", result)
        self.assertNotIn("bad()", result)
        self.assertIn("OpenAI", result)
        self.assertIn("GPT-5", result)

    def test_clean_text_empty(self):
        self.assertEqual(self.clean_text(""), "")

    def test_clean_text_no_html_strip(self):
        html = "<b>bold</b>"
        result = self.clean_text(html, strip_html=False)
        self.assertIn("<b>", result)


# ── Language detector tests ───────────────────────────────────────────────────


class TestLanguageDetector(unittest.TestCase):

    def setUp(self):
        from ai_engine.nlp.language_detector import detect_language, is_english

        self.detect_language = detect_language
        self.is_english = is_english

    def test_short_text_returns_english(self):
        lang, conf = self.detect_language("hi")
        self.assertEqual(lang, "en")

    def test_empty_text_returns_english(self):
        lang, conf = self.detect_language("")
        self.assertEqual(lang, "en")

    @patch("ai_engine.nlp.language_detector.detect_language", return_value=("en", 0.99))
    def test_is_english_true(self, mock_detect):
        from ai_engine.nlp import language_detector as ld

        result = ld.is_english("This is an English sentence about machine learning.")
        self.assertIsInstance(result, bool)

    @patch("ai_engine.nlp.language_detector.detect_language", return_value=("fr", 0.98))
    def test_is_english_false_for_french(self, mock_detect):
        from ai_engine.nlp import language_detector as ld

        result = ld.is_english("Ceci est une phrase en français.")
        self.assertFalse(result)

    def test_detect_language_import_error(self):
        """Should return unknown gracefully if langdetect is unavailable."""
        with patch.dict("sys.modules", {"langdetect": None}):
            # The function should not raise
            lang, conf = self.detect_language(
                "Some text here to test detection fallback"
            )
            self.assertIsInstance(lang, str)
            self.assertIsInstance(conf, float)


# ── Keyword extractor tests ───────────────────────────────────────────────────


class TestKeywordExtractor(unittest.TestCase):

    def setUp(self):
        from ai_engine.nlp.keyword_extractor import extract_keywords

        self.extract_keywords = extract_keywords

    def test_returns_list(self):
        with (
            patch(
                "ai_engine.nlp.keyword_extractor._extract_keybert",
                return_value=[("machine learning", 0.9)],
            ),
            patch(
                "ai_engine.nlp.keyword_extractor._extract_yake",
                return_value=[("deep learning", 0.85)],
            ),
        ):
            result = self.extract_keywords(
                "Machine learning and deep learning are popular AI topics.", top_n=5
            )
            self.assertIsInstance(result, list)

    def test_returns_strings(self):
        with (
            patch(
                "ai_engine.nlp.keyword_extractor._extract_keybert",
                return_value=[("neural networks", 0.8)],
            ),
            patch(
                "ai_engine.nlp.keyword_extractor._extract_yake",
                return_value=[("deep learning", 0.75)],
            ),
        ):
            result = self.extract_keywords(
                "Neural networks power modern deep learning systems.", top_n=5
            )
            for kw in result:
                self.assertIsInstance(kw, str)

    def test_empty_text_returns_empty(self):
        result = self.extract_keywords("")
        self.assertEqual(result, [])

    def test_short_text_returns_empty(self):
        result = self.extract_keywords("hello world")
        self.assertEqual(result, [])

    def test_respects_top_n(self):
        with (
            patch(
                "ai_engine.nlp.keyword_extractor._extract_keybert",
                return_value=[(f"keyword{i}", 0.9 - i * 0.05) for i in range(10)],
            ),
            patch("ai_engine.nlp.keyword_extractor._extract_yake", return_value=[]),
        ):
            result = self.extract_keywords("some long text " * 20, top_n=3)
            self.assertLessEqual(len(result), 3)

    def test_keybert_failure_falls_back_to_yake(self):
        with (
            patch("ai_engine.nlp.keyword_extractor._extract_keybert", return_value=[]),
            patch(
                "ai_engine.nlp.keyword_extractor._extract_yake",
                return_value=[("open source", 0.8), ("python", 0.7)],
            ),
        ):
            result = self.extract_keywords(
                "open source python machine learning project " * 5
            )
            self.assertGreater(len(result), 0)

    def test_deduplication(self):
        """Same keyword from both extractors should appear only once."""
        with (
            patch(
                "ai_engine.nlp.keyword_extractor._extract_keybert",
                return_value=[("machine learning", 0.9)],
            ),
            patch(
                "ai_engine.nlp.keyword_extractor._extract_yake",
                return_value=[("machine learning", 0.85)],
            ),
        ):
            result = self.extract_keywords("machine learning is the future " * 10)
            self.assertEqual(result.count("machine learning"), 1)


# ── Topic classifier tests ────────────────────────────────────────────────────


class TestTopicClassifier(unittest.TestCase):

    def setUp(self):
        from ai_engine.nlp.topic_classifier import (
            TECH_TOPICS,
            classify_topic,
            classify_topic_scores,
        )

        self.classify_topic = classify_topic
        self.classify_topic_scores = classify_topic_scores
        self.TECH_TOPICS = TECH_TOPICS

    def test_returns_tuple(self):
        mock_pipeline = MagicMock(
            return_value={
                "labels": ["Machine Learning", "Data Science"],
                "scores": [0.87, 0.10],
            }
        )
        with patch(
            "ai_engine.nlp.topic_classifier._get_classifier", return_value=mock_pipeline
        ):
            topic, score = self.classify_topic(
                "Deep learning model training on GPU clusters."
            )
            self.assertIsInstance(topic, str)
            self.assertIsInstance(score, float)

    def test_returns_correct_topic(self):
        mock_pipeline = MagicMock(
            return_value={
                "labels": ["Machine Learning", "Web Development"],
                "scores": [0.91, 0.05],
            }
        )
        with patch(
            "ai_engine.nlp.topic_classifier._get_classifier", return_value=mock_pipeline
        ):
            topic, score = self.classify_topic("Training neural networks with PyTorch.")
            self.assertEqual(topic, "Machine Learning")
            self.assertAlmostEqual(score, 0.91)

    def test_low_confidence_returns_technology(self):
        mock_pipeline = MagicMock(
            return_value={
                "labels": ["Machine Learning"],
                "scores": [0.10],  # Below MIN_CONFIDENCE
            }
        )
        with patch(
            "ai_engine.nlp.topic_classifier._get_classifier", return_value=mock_pipeline
        ):
            topic, score = self.classify_topic("Some vague text about stuff.")
            self.assertEqual(topic, "Technology")

    def test_empty_text_returns_default(self):
        topic, score = self.classify_topic("")
        self.assertEqual(topic, "Technology")

    def test_unavailable_classifier_returns_default(self):
        with patch("ai_engine.nlp.topic_classifier._get_classifier", return_value=None):
            topic, score = self.classify_topic("Cloud computing deployment pipeline.")
            self.assertEqual(topic, "Technology")
            self.assertEqual(score, 0.0)

    def test_tech_topics_list_not_empty(self):
        self.assertGreater(len(self.TECH_TOPICS), 5)

    def test_classify_topic_scores_returns_list(self):
        mock_pipeline = MagicMock(
            return_value={
                "labels": ["Machine Learning", "Data Science", "Cloud Computing"],
                "scores": [0.80, 0.12, 0.08],
            }
        )
        with patch(
            "ai_engine.nlp.topic_classifier._get_classifier", return_value=mock_pipeline
        ):
            results = self.classify_topic_scores(
                "AI and machine learning are transforming the world of technology."
            )
            self.assertIsInstance(results, list)
            self.assertGreater(len(results), 0)


# ── Sentiment analyzer tests ──────────────────────────────────────────────────


class TestSentimentAnalyzer(unittest.TestCase):

    def setUp(self):
        from ai_engine.nlp.sentiment_analyzer import (
            analyze_sentiment,
            sentiment_to_score,
        )

        self.analyze_sentiment = analyze_sentiment
        self.sentiment_to_score = sentiment_to_score

    def test_returns_tuple(self):
        mock_pipe = MagicMock(return_value=[{"label": "LABEL_2", "score": 0.95}])
        with patch(
            "ai_engine.nlp.sentiment_analyzer._get_pipeline", return_value=mock_pipe
        ):
            label, score = self.analyze_sentiment("This is an amazing breakthrough!")
            self.assertIsInstance(label, str)
            self.assertIsInstance(score, float)

    def test_positive_sentiment(self):
        mock_pipe = MagicMock(return_value=[{"label": "LABEL_2", "score": 0.95}])
        with patch(
            "ai_engine.nlp.sentiment_analyzer._get_pipeline", return_value=mock_pipe
        ):
            label, score = self.analyze_sentiment("Great progress in AI research!")
            self.assertEqual(label, "POSITIVE")
            self.assertGreater(score, 0.5)

    def test_negative_sentiment(self):
        mock_pipe = MagicMock(return_value=[{"label": "LABEL_0", "score": 0.88}])
        with patch(
            "ai_engine.nlp.sentiment_analyzer._get_pipeline", return_value=mock_pipe
        ):
            label, score = self.analyze_sentiment(
                "This bug is terrible and broke production."
            )
            self.assertEqual(label, "NEGATIVE")

    def test_neutral_sentiment(self):
        mock_pipe = MagicMock(return_value=[{"label": "LABEL_1", "score": 0.76}])
        with patch(
            "ai_engine.nlp.sentiment_analyzer._get_pipeline", return_value=mock_pipe
        ):
            label, score = self.analyze_sentiment("Python 3.12 was released last week.")
            self.assertEqual(label, "NEUTRAL")

    def test_empty_text_returns_neutral(self):
        label, score = self.analyze_sentiment("")
        self.assertEqual(label, "NEUTRAL")
        self.assertEqual(score, 0.0)

    def test_short_text_returns_neutral(self):
        label, score = self.analyze_sentiment("hi")
        self.assertEqual(label, "NEUTRAL")

    def test_unavailable_pipeline_returns_neutral(self):
        with patch("ai_engine.nlp.sentiment_analyzer._get_pipeline", return_value=None):
            label, score = self.analyze_sentiment("Some text about technology trends.")
            self.assertEqual(label, "NEUTRAL")

    def test_sentiment_to_score_positive(self):
        score = self.sentiment_to_score("POSITIVE", 0.9)
        self.assertAlmostEqual(score, 0.9)

    def test_sentiment_to_score_negative(self):
        score = self.sentiment_to_score("NEGATIVE", 0.8)
        self.assertAlmostEqual(score, -0.8)

    def test_sentiment_to_score_neutral(self):
        score = self.sentiment_to_score("NEUTRAL", 0.7)
        self.assertEqual(score, 0.0)

    def test_score_in_range(self):
        for label, conf in [("POSITIVE", 0.9), ("NEGATIVE", 0.9), ("NEUTRAL", 0.9)]:
            score = self.sentiment_to_score(label, conf)
            self.assertGreaterEqual(score, -1.0)
            self.assertLessEqual(score, 1.0)


# ── NER tests ─────────────────────────────────────────────────────────────────


class TestNER(unittest.TestCase):

    def setUp(self):
        from ai_engine.nlp.ner import extract_entities, extract_tech_terms

        self.extract_entities = extract_entities
        self.extract_tech_terms = extract_tech_terms

    def _make_mock_ent(self, text, label_, start_char, end_char):
        ent = MagicMock()
        ent.text = text
        ent.label_ = label_
        ent.start_char = start_char
        ent.end_char = end_char
        return ent

    def _make_mock_nlp(self, entities):
        doc = MagicMock()
        doc.ents = entities
        nlp = MagicMock(return_value=doc)
        return nlp

    def test_returns_list(self):
        mock_nlp = self._make_mock_nlp([self._make_mock_ent("OpenAI", "ORG", 0, 6)])
        with patch("ai_engine.nlp.ner._get_nlp", return_value=mock_nlp):
            result = self.extract_entities("OpenAI released a new model.")
            self.assertIsInstance(result, list)

    def test_extracts_org_entity(self):
        mock_nlp = self._make_mock_nlp([self._make_mock_ent("Google", "ORG", 0, 6)])
        with patch("ai_engine.nlp.ner._get_nlp", return_value=mock_nlp):
            result = self.extract_entities("Google announced a new AI model.")
            self.assertTrue(any(e["text"] == "Google" for e in result))
            self.assertTrue(any(e["label"] == "ORG" for e in result))

    def test_filters_irrelevant_entity_types(self):
        # CARDINAL (numbers) should be filtered out
        mock_nlp = self._make_mock_nlp(
            [
                self._make_mock_ent("42", "CARDINAL", 0, 2),
                self._make_mock_ent("OpenAI", "ORG", 5, 11),
            ]
        )
        with patch("ai_engine.nlp.ner._get_nlp", return_value=mock_nlp):
            result = self.extract_entities("42 OpenAI researchers.")
            labels = [e["label"] for e in result]
            self.assertNotIn("CARDINAL", labels)
            self.assertIn("ORG", labels)

    def test_deduplication(self):
        mock_nlp = self._make_mock_nlp(
            [
                self._make_mock_ent("OpenAI", "ORG", 0, 6),
                self._make_mock_ent("OpenAI", "ORG", 20, 26),
            ]
        )
        with patch("ai_engine.nlp.ner._get_nlp", return_value=mock_nlp):
            result = self.extract_entities("OpenAI is great. OpenAI released GPT.")
            openai_entities = [e for e in result if e["text"] == "OpenAI"]
            self.assertEqual(len(openai_entities), 1)

    def test_empty_text_returns_empty(self):
        result = self.extract_entities("")
        self.assertEqual(result, [])

    def test_unavailable_model_returns_empty(self):
        with patch("ai_engine.nlp.ner._get_nlp", return_value=None):
            result = self.extract_entities("OpenAI Google Microsoft.")
            self.assertEqual(result, [])

    def test_extract_tech_terms_returns_strings(self):
        mock_nlp = self._make_mock_nlp(
            [
                self._make_mock_ent("Python", "LANGUAGE", 0, 6),
                self._make_mock_ent("GitHub", "ORG", 10, 16),
            ]
        )
        with patch("ai_engine.nlp.ner._get_nlp", return_value=mock_nlp):
            result = self.extract_tech_terms("Python on GitHub is popular.")
            self.assertIsInstance(result, list)
            for item in result:
                self.assertIsInstance(item, str)


# ── Summarizer tests ──────────────────────────────────────────────────────────


class TestSummarizer(unittest.TestCase):

    def setUp(self):
        from ai_engine.nlp.summarizer import MIN_WORDS, summarize

        self.summarize = summarize
        self.MIN_WORDS = MIN_WORDS

    def test_short_text_returned_as_is(self):
        short_text = "Hello world."
        result = self.summarize(short_text)
        self.assertEqual(result, short_text.strip())

    def test_none_on_empty_input(self):
        result = self.summarize("")
        self.assertIsNone(result)

    def test_summarizes_long_text(self):
        mock_pipe = MagicMock(
            return_value=[{"summary_text": "AI systems achieved new milestones."}]
        )
        with patch("ai_engine.nlp.summarizer._get_summarizer", return_value=mock_pipe):
            long_text = "Artificial intelligence " * 60
            result = self.summarize(long_text)
            self.assertIsNotNone(result)
            self.assertIsInstance(result, str)
            self.assertGreater(len(result), 0)

    def test_unavailable_model_returns_none(self):
        with patch("ai_engine.nlp.summarizer._get_summarizer", return_value=None):
            long_text = "Machine learning deep learning neural networks. " * 20
            result = self.summarize(long_text)
            self.assertIsNone(result)

    def test_summary_generated_correctly(self):
        expected = "OpenAI released a powerful new language model."
        mock_pipe = MagicMock(return_value=[{"summary_text": expected}])
        with patch("ai_engine.nlp.summarizer._get_summarizer", return_value=mock_pipe):
            text = "OpenAI " * 80
            result = self.summarize(text)
            self.assertEqual(result, expected)


# ── Pipeline integration tests ────────────────────────────────────────────────


class TestNLPPipeline(unittest.TestCase):

    def setUp(self):
        from ai_engine.nlp.pipeline import NLPResult, run_pipeline

        self.run_pipeline = run_pipeline
        self.NLPResult = NLPResult

    def test_returns_nlp_result(self):
        with (
            patch(
                "ai_engine.nlp.pipeline.clean_text",
                return_value="clean text about AI " * 10,
            ),
            patch("ai_engine.nlp.pipeline.detect_language", return_value=("en", 0.99)),
            patch(
                "ai_engine.nlp.pipeline.extract_keywords",
                return_value=["machine learning", "AI"],
            ),
            patch(
                "ai_engine.nlp.pipeline.classify_topic",
                return_value=("Machine Learning", 0.88),
            ),
            patch(
                "ai_engine.nlp.pipeline.analyze_sentiment",
                return_value=("POSITIVE", 0.92),
            ),
            patch("ai_engine.nlp.pipeline.sentiment_to_score", return_value=0.92),
            patch(
                "ai_engine.nlp.pipeline.extract_entities",
                return_value=[{"text": "OpenAI", "label": "ORG"}],
            ),
        ):
            result = self.run_pipeline(
                "Machine learning is transforming AI.", title="AI News"
            )
            self.assertIsInstance(result, self.NLPResult)

    def test_english_text_not_skipped(self):
        with (
            patch(
                "ai_engine.nlp.pipeline.clean_text",
                return_value="machine learning ai " * 10,
            ),
            patch("ai_engine.nlp.pipeline.detect_language", return_value=("en", 0.99)),
            patch("ai_engine.nlp.pipeline.extract_keywords", return_value=["ml"]),
            patch(
                "ai_engine.nlp.pipeline.classify_topic",
                return_value=("Machine Learning", 0.9),
            ),
            patch(
                "ai_engine.nlp.pipeline.analyze_sentiment",
                return_value=("POSITIVE", 0.8),
            ),
            patch("ai_engine.nlp.pipeline.sentiment_to_score", return_value=0.8),
            patch("ai_engine.nlp.pipeline.extract_entities", return_value=[]),
        ):
            result = self.run_pipeline("Machine learning is transforming AI research.")
            self.assertFalse(result.skipped)

    def test_non_english_text_skipped(self):
        with (
            patch(
                "ai_engine.nlp.pipeline.clean_text",
                return_value="Ceci est une phrase française " * 5,
            ),
            patch("ai_engine.nlp.pipeline.detect_language", return_value=("fr", 0.97)),
        ):
            result = self.run_pipeline("Ceci est une phrase française sur l'IA.")
            self.assertTrue(result.skipped)
            self.assertIn("fr", result.skip_reason)

    def test_empty_text_skipped(self):
        result = self.run_pipeline("")
        self.assertTrue(result.skipped)

    def test_pipeline_fields_populated(self):
        with (
            patch(
                "ai_engine.nlp.pipeline.clean_text",
                return_value="ai ml cloud devops " * 10,
            ),
            patch("ai_engine.nlp.pipeline.detect_language", return_value=("en", 0.99)),
            patch(
                "ai_engine.nlp.pipeline.extract_keywords", return_value=["ai", "cloud"]
            ),
            patch(
                "ai_engine.nlp.pipeline.classify_topic",
                return_value=("Cloud Computing", 0.85),
            ),
            patch(
                "ai_engine.nlp.pipeline.analyze_sentiment",
                return_value=("NEUTRAL", 0.70),
            ),
            patch("ai_engine.nlp.pipeline.sentiment_to_score", return_value=0.0),
            patch(
                "ai_engine.nlp.pipeline.extract_entities",
                return_value=[{"text": "AWS", "label": "ORG"}],
            ),
        ):
            result = self.run_pipeline("AI and cloud computing with DevOps.")
            self.assertEqual(result.topic, "Cloud Computing")
            self.assertIn("ai", result.keywords)
            self.assertEqual(result.sentiment_label, "NEUTRAL")
            self.assertEqual(result.sentiment_score, 0.0)
            self.assertTrue(len(result.entities) > 0)

    def test_selective_steps(self):
        """Pipeline should respect run_* flags."""
        with (
            patch(
                "ai_engine.nlp.pipeline.clean_text",
                return_value="python programming " * 10,
            ),
            patch("ai_engine.nlp.pipeline.detect_language", return_value=("en", 0.99)),
            patch(
                "ai_engine.nlp.pipeline.extract_keywords", return_value=["python"]
            ) as mock_kw,
            patch(
                "ai_engine.nlp.pipeline.classify_topic",
                return_value=("Programming", 0.9),
            ) as mock_topic,
            patch(
                "ai_engine.nlp.pipeline.analyze_sentiment",
                return_value=("POSITIVE", 0.8),
            ) as mock_sent,
            patch("ai_engine.nlp.pipeline.sentiment_to_score", return_value=0.8),
            patch(
                "ai_engine.nlp.pipeline.extract_entities", return_value=[]
            ) as mock_ner,
        ):
            result = self.run_pipeline(
                "Python is great.",
                run_keywords=False,
                run_topic=False,
                run_sentiment=True,
                run_ner=False,
            )
            mock_kw.assert_not_called()
            mock_topic.assert_not_called()
            mock_ner.assert_not_called()
            mock_sent.assert_called_once()

    def test_summarization_included_in_pipeline(self):
        """Phase 2.2 — pipeline should populate result.summary via BART."""
        expected_summary = "AI systems are transforming modern technology."
        with (
            patch(
                "ai_engine.nlp.pipeline.clean_text",
                return_value="ai machine learning " * 15,
            ),
            patch("ai_engine.nlp.pipeline.detect_language", return_value=("en", 0.99)),
            patch("ai_engine.nlp.pipeline.extract_keywords", return_value=["ai"]),
            patch(
                "ai_engine.nlp.pipeline.classify_topic",
                return_value=("Machine Learning", 0.9),
            ),
            patch(
                "ai_engine.nlp.pipeline.analyze_sentiment",
                return_value=("POSITIVE", 0.85),
            ),
            patch("ai_engine.nlp.pipeline.sentiment_to_score", return_value=0.85),
            patch("ai_engine.nlp.pipeline.extract_entities", return_value=[]),
            patch("ai_engine.nlp.summarizer.summarize", return_value=expected_summary),
        ):
            result = self.run_pipeline(
                "AI machine learning is transforming modern technology in remarkable ways.",
                run_summarization=True,
            )
            self.assertEqual(result.summary, expected_summary)

    def test_summarization_disabled_by_flag(self):
        """Phase 2.2 — run_summarization=False must skip summarization."""
        with (
            patch(
                "ai_engine.nlp.pipeline.clean_text",
                return_value="ai machine learning " * 15,
            ),
            patch("ai_engine.nlp.pipeline.detect_language", return_value=("en", 0.99)),
            patch("ai_engine.nlp.pipeline.extract_keywords", return_value=["ai"]),
            patch(
                "ai_engine.nlp.pipeline.classify_topic",
                return_value=("Machine Learning", 0.9),
            ),
            patch(
                "ai_engine.nlp.pipeline.analyze_sentiment",
                return_value=("POSITIVE", 0.85),
            ),
            patch("ai_engine.nlp.pipeline.sentiment_to_score", return_value=0.85),
            patch("ai_engine.nlp.pipeline.extract_entities", return_value=[]),
        ):
            result = self.run_pipeline(
                "AI machine learning research.",
                run_summarization=False,
            )
            self.assertIsNone(result.summary)

    def test_pipeline_summary_field_exists(self):
        """NLPResult dataclass must have a summary field (Phase 2.2)."""
        result = self.NLPResult()
        self.assertTrue(hasattr(result, "summary"))
        self.assertIsNone(result.summary)


# ── Summarization Celery task tests ───────────────────────────────────────────


class TestSummarizeArticleTask(unittest.TestCase):
    """
    Phase 2.2 — unit tests for the summarize_article Celery task logic.

    We test the inner logic directly (without Django ORM or Celery broker)
    by mocking the Article model import inside the task function.
    """

    def _make_article(self, content="", summary="", nlp_processed=False, title=""):
        article = MagicMock()
        article.id = "test-uuid-1234"
        article.content = content
        article.title = title  # explicit str — MagicMock would be truthy!
        article.summary = summary
        article.nlp_processed = nlp_processed
        article.save = MagicMock()
        return article

    def _make_self(self):
        """Create a minimal mock of the Celery task `self` object."""
        self_mock = MagicMock()
        self_mock.request.id = "test-task-id"
        self_mock.request.retries = 0
        self_mock.retry.side_effect = Exception("retry called")
        return self_mock

    def _call_task(self, task_fn, *args, **kwargs):
        """
        Call a bound Celery task's underlying function directly.
        __wrapped__ is the raw function without the Celery bind injection,
        so it does NOT receive `self` — just the task arguments.
        """
        return task_fn.__wrapped__(*args, **kwargs)

    def test_skips_when_already_summarized(self):
        """Task must return skipped when article already has a summary and force=False."""
        article = self._make_article(content="some content", summary="existing summary")

        mock_article_cls = MagicMock()
        mock_article_cls.objects.get.return_value = article
        mock_article_cls.DoesNotExist = type("DoesNotExist", (Exception,), {})

        import builtins

        import apps.articles.tasks as tasks_mod

        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "apps.articles.models":
                mod = MagicMock()
                mod.Article = mock_article_cls
                return mod
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            result = self._call_task(
                tasks_mod.summarize_article, str(article.id), False
            )
            self.assertEqual(result["status"], "skipped")
            self.assertEqual(result["reason"], "already_summarized")

    def test_skips_when_no_content(self):
        """Task must return skipped when article has no content."""
        article = self._make_article(content="", summary="")

        mock_article_cls = MagicMock()
        mock_article_cls.objects.get.return_value = article
        mock_article_cls.DoesNotExist = type("DoesNotExist", (Exception,), {})

        import builtins

        import apps.articles.tasks as tasks_mod

        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "apps.articles.models":
                mod = MagicMock()
                mod.Article = mock_article_cls
                return mod
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            result = self._call_task(
                tasks_mod.summarize_article, str(article.id), False
            )
            self.assertEqual(result["status"], "skipped")
            # The task may return "no_content" or "no_text" depending on which
            # guard fires first (title-less vs. content-less path)
            self.assertIn(result["reason"], ("no_content", "no_text"))


if __name__ == "__main__":
    unittest.main()
