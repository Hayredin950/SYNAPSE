from rest_framework import serializers

from .models import Article, Source


class SourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Source
        fields = ["id", "name", "url", "source_type", "is_active", "last_scraped_at"]


class ArticleListSerializer(serializers.ModelSerializer):
    """
    Serializer for article list views.
    Includes summary (Gemini-generated, Phase 2.2) and nlp_processed flag
    so the frontend can show AI badges and summary text on cards.

    Also includes `excerpt` — the first ~180 characters of content (or the
    title if no content is available).  The frontend shows this instantly
    while the AI summary is still being generated, then swaps it out when
    the real summary arrives via polling.
    """

    source = SourceSerializer(read_only=True)
    excerpt = serializers.SerializerMethodField()

    source_type = serializers.SerializerMethodField()

    class Meta:
        model = Article
        fields = [
            "id",
            "title",
            "summary",
            "excerpt",
            "url",
            "source",
            "source_type",
            "author",
            "published_at",
            "topic",
            "tags",
            "keywords",
            "sentiment_score",
            "trending_score",
            "view_count",
            "scraped_at",
            "nlp_processed",
        ]

    def get_source_type(self, obj) -> str:
        """Return the source_type directly for use in the frontend card badge."""
        return obj.source.source_type if obj.source else ""

    def get_excerpt(self, obj) -> str:
        """
        Return a human-readable excerpt for instant display while AI summary
        is being generated.

        Priority:
          1. metadata['excerpt'] — fetched from og:description / meta description
             by the fetch_article_excerpt Celery task (best quality)
          2. First 200 chars of article content (if available)
          3. Empty string — frontend will just show the title (which is already
             displayed as the card heading, so no duplication)
        """
        # 1. Fetched web excerpt (og:description / meta description)
        metadata_excerpt = (obj.metadata or {}).get("excerpt", "")
        if metadata_excerpt and len(metadata_excerpt) > 30:
            return metadata_excerpt

        # 2. First 200 chars of body content
        content = (obj.content or "").strip()
        if content:
            import re

            clean = re.sub(r"\s+", " ", content)
            return clean[:200].rsplit(" ", 1)[0] + "…" if len(clean) > 200 else clean

        # 3. No excerpt available yet — return empty so frontend shows nothing
        # (avoids repeating the title which is already shown as the card heading)
        return ""


class ArticleDetailSerializer(serializers.ModelSerializer):
    """
    Full article serializer for detail views.
    Exposes all fields including BART summary, NLP metadata and entities
    stored in the metadata JSON field.
    """

    source = SourceSerializer(read_only=True)

    # Convenience read-only fields surfaced from the metadata JSON blob
    entities = serializers.SerializerMethodField()
    language = serializers.SerializerMethodField()
    topic_confidence = serializers.SerializerMethodField()

    class Meta:
        model = Article
        fields = "__all__"

    def get_entities(self, obj):
        return (obj.metadata or {}).get("entities", [])

    def get_language(self, obj):
        return (obj.metadata or {}).get("language", "")

    def get_topic_confidence(self, obj):
        return (obj.metadata or {}).get("topic_confidence", None)
