from rest_framework import serializers

from .models import Tweet


class TweetListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tweet
        fields = [
            "id",
            "tweet_id",
            "text",
            "author_username",
            "author_display_name",
            "author_profile_image",
            "author_verified",
            "author_followers",
            "retweet_count",
            "like_count",
            "reply_count",
            "quote_count",
            "view_count",
            "bookmark_count",
            "posted_at",
            "scraped_at",
            "hashtags",
            "mentions",
            "media_urls",
            "urls",
            "is_retweet",
            "is_reply",
            "is_quote",
            "conversation_id",
            "in_reply_to_user",
            "lang",
            "url",
            "source_label",
            "topic",
            "trending_score",
            "sentiment_score",
            "metadata",
        ]


class TweetDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tweet
        fields = "__all__"
