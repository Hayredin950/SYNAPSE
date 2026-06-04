from apps.articles.models import Article, Source

from django.test import TestCase


class ArticleModelTest(TestCase):
    def setUp(self):
        self.source = Source.objects.create(
            name="Hacker News", url="https://news.ycombinator.com", source_type="news"
        )

    def test_article_creation(self):
        article = Article.objects.create(
            title="Test Article", url="https://example.com/article1", source=self.source
        )
        self.assertEqual(str(article), "Test Article")
        self.assertIsNotNone(article.url_hash)

    def test_url_hash_generated(self):
        import hashlib

        article = Article.objects.create(
            title="Hash Test", url="https://example.com/hash-test", source=self.source
        )
        expected = hashlib.sha256("https://example.com/hash-test".encode()).hexdigest()
        self.assertEqual(article.url_hash, expected)

    def test_duplicate_url_rejected(self):
        Article.objects.create(
            title="Dup 1", url="https://example.com/dup", source=self.source
        )
        from django.db import IntegrityError

        with self.assertRaises(IntegrityError):
            Article.objects.create(
                title="Dup 2", url="https://example.com/dup", source=self.source
            )
