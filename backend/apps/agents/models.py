import uuid

from django.conf import settings
from django.db import models


class AgentTask(models.Model):
    class TaskStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="agent_tasks"
    )
    task_type = models.CharField(max_length=200)
    prompt = models.TextField()
    status = models.CharField(
        max_length=20, choices=TaskStatus.choices, default=TaskStatus.PENDING
    )
    result = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    celery_task_id = models.CharField(max_length=200, blank=True)
    tokens_used = models.IntegerField(default=0)
    cost_usd = models.DecimalField(max_digits=10, decimal_places=6, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "agent_tasks"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.task_type} — {self.status}"


# ── TASK-306-B1: Prompt Library ───────────────────────────────────────────────


class PromptTemplate(models.Model):
    """Community-shared prompt templates for the Prompt Library (TASK-306)."""

    class Category(models.TextChoices):
        RESEARCH = "research", "Research"
        CODING = "coding", "Coding"
        WRITING = "writing", "Writing"
        ANALYSIS = "analysis", "Analysis"
        BUSINESS = "business", "Business"
        CREATIVE = "creative", "Creative"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    content = models.TextField()  # the actual prompt text
    category = models.CharField(
        max_length=50, choices=Category.choices, default=Category.RESEARCH
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="prompt_templates",
    )
    is_public = models.BooleanField(default=True)
    use_count = models.PositiveIntegerField(default=0)
    upvotes = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "prompt_templates"
        ordering = ["-upvotes", "-use_count", "-created_at"]
        indexes = [
            models.Index(fields=["category", "-upvotes"], name="pt_cat_upvotes_idx"),
            models.Index(
                fields=["author", "-created_at"], name="pt_author_created_idx"
            ),
            models.Index(
                fields=["is_public", "-created_at"], name="pt_public_created_idx"
            ),
        ]

    def __str__(self):
        return f"{self.title} ({self.category})"


class PromptUpvote(models.Model):
    """One upvote per user per prompt (toggle model)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="prompt_upvotes",
    )
    prompt = models.ForeignKey(
        PromptTemplate, on_delete=models.CASCADE, related_name="upvote_records"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "prompt_upvotes"
        unique_together = [("user", "prompt")]


# ── TASK-601-B1: Research Mode ────────────────────────────────────────────────


class ResearchSession(models.Model):
    """Tracks a deep-research session created by the Plan-and-Execute agent."""

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        COMPLETE = "complete", "Complete"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="research_sessions",
    )
    query = models.TextField()
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.QUEUED, db_index=True
    )
    report = models.TextField(blank=True)  # Final synthesised report (markdown)
    sources = models.JSONField(default=list)  # [{"title":…,"url":…,"type":…}]
    sub_questions = models.JSONField(default=list)  # ["sub-q1", "sub-q2", …]
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "research_sessions"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"], name="rs_user_created_idx"),
            models.Index(fields=["status"], name="rs_status_idx"),
        ]

    def __str__(self):
        return f"ResearchSession({self.query[:60]}, {self.status})"
