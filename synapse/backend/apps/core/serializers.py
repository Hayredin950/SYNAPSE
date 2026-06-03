from django.contrib.contenttypes.models import ContentType
from rest_framework import serializers

from .models import Collection, UserBookmark


class BookmarkSerializer(serializers.ModelSerializer):
    content_type_name = serializers.SerializerMethodField()
    content_object_title = serializers.SerializerMethodField()
    content_object_url = serializers.SerializerMethodField()

    class Meta:
        model = UserBookmark
        fields = [
            "id",
            "content_type",
            "content_type_name",
            "object_id",
            "content_object_title",
            "content_object_url",
            "notes",
            "tags",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_content_type_name(self, obj):
        return obj.content_type.model

    def get_content_object_title(self, obj):
        content_obj = obj.content_object
        if content_obj:
            return getattr(
                content_obj, "title", getattr(content_obj, "name", str(content_obj))
            )
        return None

    def get_content_object_url(self, obj):
        content_obj = obj.content_object
        if content_obj:
            return getattr(content_obj, "url", None)
        return None


class CollectionSerializer(serializers.ModelSerializer):
    bookmark_count = serializers.SerializerMethodField()
    bookmarks = BookmarkSerializer(many=True, read_only=True)

    class Meta:
        model = Collection
        fields = [
            "id",
            "name",
            "description",
            "is_public",
            "bookmark_count",
            "bookmarks",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_bookmark_count(self, obj):
        return obj.bookmarks.count()


class CollectionListSerializer(serializers.ModelSerializer):
    bookmark_count = serializers.SerializerMethodField()

    class Meta:
        model = Collection
        fields = [
            "id",
            "name",
            "description",
            "is_public",
            "bookmark_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_bookmark_count(self, obj):
        return obj.bookmarks.count()
