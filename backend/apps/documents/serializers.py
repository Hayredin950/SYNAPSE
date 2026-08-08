"""
backend.apps.documents.serializers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
DRF serializers for the GeneratedDocument model.

Phase 5.2 — Document Generation (Week 14)
"""

from rest_framework import serializers

from .models import GeneratedDocument


class ProjectGenerateSerializer(serializers.Serializer):
    """Input serializer for project scaffold generation requests (Phase 5.3)."""

    VALID_PROJECT_TYPES = [
        "django",
        "fastapi",
        "nextjs",
        "datascience",
        "react_lib",
        "html_template",
    ]
    VALID_FEATURES = ["auth", "testing", "ci_cd"]

    project_type = serializers.ChoiceField(
        choices=VALID_PROJECT_TYPES,
        help_text="Project template type: django, fastapi, nextjs, datascience, or react_lib",
    )
    name = serializers.CharField(
        max_length=100,
        help_text="Project name (kebab-case recommended, e.g. 'my-api')",
    )
    features = serializers.ListField(
        child=serializers.ChoiceField(choices=VALID_FEATURES),
        required=False,
        allow_empty=True,
        default=list,
        help_text="Optional feature flags: 'auth', 'testing', 'ci_cd'",
    )
    description = serializers.CharField(
        max_length=2000,
        required=False,
        allow_blank=True,
        default="",
        help_text=(
            "Optional free-text description of what the project should do. "
            "Included in the generated README and used to customise the scaffold."
        ),
    )

    def validate_name(self, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise serializers.ValidationError(
                "Project name must be at least 2 characters."
            )
        # Allow alphanumeric, hyphens, underscores
        import re

        if not re.match(r"^[a-zA-Z0-9_\-]+$", value):
            raise serializers.ValidationError(
                "Project name may only contain letters, numbers, hyphens, and underscores."
            )
        return value


class DocumentGenerateSerializer(serializers.Serializer):
    """Input serializer for document generation requests."""

    VALID_DOC_TYPES = ["pdf", "ppt", "word", "markdown"]

    doc_type = serializers.ChoiceField(
        choices=VALID_DOC_TYPES,
        help_text="Document format: pdf, ppt, word, markdown, or html",
    )
    title = serializers.CharField(
        max_length=500,
        help_text="Document title",
    )
    prompt = serializers.CharField(
        max_length=8000,
        help_text=(
            "Natural language prompt describing what to generate. "
            "The AI agent will use this to structure the content."
        ),
    )
    sections = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        allow_empty=True,
        help_text=(
            "Optional pre-structured sections. Each dict has 'heading' and 'content'. "
            "If omitted, the agent generates sections from the prompt."
        ),
    )
    subtitle = serializers.CharField(
        max_length=300,
        required=False,
        allow_blank=True,
        default="",
        help_text="Optional subtitle (PDF cover page / PPT title slide)",
    )
    author = serializers.CharField(
        max_length=200,
        required=False,
        allow_blank=True,
        default="SYNAPSE AI",
        help_text="Author name shown in document metadata and footer",
    )
    model = serializers.CharField(
        max_length=200,
        required=False,
        allow_blank=True,
        default="",
        help_text=(
            "Optional OpenRouter model override for HTML generation, "
            "e.g. 'openai/gpt-4o', 'anthropic/claude-3.5-sonnet'. "
            "Defaults to OPENROUTER_MODEL env var or gpt-4o-mini."
        ),
    )
    content_types = serializers.ListField(
        child=serializers.ChoiceField(
            choices=["articles", "papers", "repositories", "videos"]
        ),
        required=False,
        allow_empty=True,
        default=list,
        help_text=(
            "Filter RAG retrieval to specific content types. "
            "Options: 'articles', 'papers', 'repositories', 'videos'. "
            "Defaults to all types."
        ),
    )
    source_item_ids = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        allow_empty=True,
        default=list,
        help_text=(
            "Pin specific Synapse items as source context. "
            "Each dict must have 'id' (UUID) and 'type' "
            "('article', 'paper', 'repository', 'video'). "
            "Example: [{'id': 'uuid-here', 'type': 'paper'}]. "
            "When provided, skips vector search and uses these items directly."
        ),
    )

    def validate_title(self, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise serializers.ValidationError("Title must be at least 3 characters.")
        return value

    def validate_prompt(self, value: str) -> str:
        value = value.strip()
        if len(value) < 10:
            raise serializers.ValidationError("Prompt must be at least 10 characters.")
        return value


class GeneratedDocumentSerializer(serializers.ModelSerializer):
    """Full serializer for reading document records."""

    download_url = serializers.SerializerMethodField()
    sources_used = serializers.JSONField(source="sources_metadata", read_only=True)

    class Meta:
        model = GeneratedDocument
        fields = [
            "id",
            "title",
            "doc_type",
            "file_path",
            "cloud_url",
            "file_size_bytes",
            "agent_prompt",
            "download_url",
            "metadata",
            "sources_used",
            "created_at",
            "version",
            "parent",
        ]
        read_only_fields = fields

    def get_download_url(self, obj: GeneratedDocument) -> str:
        """Return the download URL relative to the API host."""
        request = self.context.get("request")
        if obj.file_path:
            path = f"/api/v1/documents/{obj.id}/download/"
            if request:
                return request.build_absolute_uri(path)
            return path
        return obj.cloud_url or ""


class GeneratedDocumentListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views."""

    class Meta:
        model = GeneratedDocument
        fields = [
            "id",
            "title",
            "doc_type",
            "file_size_bytes",
            "created_at",
        ]
        read_only_fields = fields
