import uuid

from apps.users.models import User

from django.db import models


class GeneratedDocument(models.Model):
    class DocType(models.TextChoices):
        PDF = "pdf", "PDF"
        PPT = "ppt", "PowerPoint"
        WORD = "word", "Word"
        MARKDOWN = "markdown", "Markdown"
        HTML = "html", "HTML"
        PROJECT = "project", "Project Scaffold"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="documents")
    title = models.CharField(max_length=500)
    doc_type = models.CharField(max_length=20, choices=DocType.choices)
    file_path = models.CharField(max_length=1000, blank=True)
    cloud_url = models.URLField(max_length=1000, blank=True)
    file_size_bytes = models.BigIntegerField(default=0)
    agent_prompt = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)
    version = models.PositiveIntegerField(default=1)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="versions",
    )
    # TASK-006-B4: scope documents to an organization workspace
    organization = models.ForeignKey(
        "organizations.Organization",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="documents",
        help_text="If set, this document belongs to an org workspace.",
    )
    # RAG: stores which Synapse sources were used as context during generation
    sources_metadata = models.JSONField(
        default=list,
        blank=True,
        help_text="List of Synapse sources (articles/papers/repos/videos) used as RAG context.",
    )

    class Meta:
        db_table = "generated_documents"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} ({self.doc_type})"
