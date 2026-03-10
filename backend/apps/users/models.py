import hashlib
import secrets
import uuid
import uuid as _uuid

from django.contrib.auth.models import AbstractUser
from django.db import models


def _generate_api_key() -> str:
    return f"sk-syn-{secrets.token_urlsafe(24)}"


class APIKey(models.Model):
    """
    TASK-605-B1: Public API Key for developer access.
    Key format: sk-syn-{32 chars}
    Only the SHA-256 hash is stored; full key shown once on creation.
    """

    id = models.UUIDField(primary_key=True, default=_uuid.uuid4, editable=False)
    user = models.ForeignKey(
        "User",
        on_delete=models.CASCADE,
        related_name="api_keys",
    )
    name = models.CharField(max_length=100)
    key_prefix = models.CharField(max_length=16)  # first 12 chars for display
    key_hash = models.CharField(max_length=64, unique=True)  # SHA-256 of full key
    scopes = models.JSONField(default=list)  # e.g. ["read:content", "write:ai"]
    last_used = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "api_keys"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.key_prefix}…)"

    @classmethod
    def create_key(
        cls, user, name: str, scopes: list | None = None
    ) -> tuple["APIKey", str]:
        """
        Generate a new API key. Returns (APIKey instance, raw_key).
        The raw_key is shown once — only the hash is stored.
        """
        raw_key = _generate_api_key()
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        key_prefix = raw_key[:12]
        instance = cls.objects.create(
            user=user,
            name=name,
            key_prefix=key_prefix,
            key_hash=key_hash,
            scopes=scopes or [],
        )
        return instance, raw_key

    @classmethod
    def authenticate(cls, raw_key: str) -> "APIKey | None":
        """Look up an APIKey by raw value. Updates last_used on success."""
        from django.utils import timezone

        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        try:
            api_key = cls.objects.select_related("user").get(
                key_hash=key_hash, is_active=True
            )
            if api_key.expires_at and api_key.expires_at < timezone.now():
                return None
            cls.objects.filter(pk=api_key.pk).update(last_used=timezone.now())
            return api_key
        except cls.DoesNotExist:
            return None


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        PREMIUM = "premium", "Premium"
        USER = "user", "User"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.USER)
    avatar_url = models.URLField(max_length=500, blank=True)
    preferences = models.JSONField(default=dict, blank=True)
    bio = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # ── Email verification ────────────────────────────────────
    email_verified = models.BooleanField(default=False)
    email_verification_token = models.UUIDField(
        null=True, blank=True, default=uuid.uuid4
    )
    # ── Social auth ───────────────────────────────────────────
    google_id = models.CharField(max_length=255, blank=True, unique=True, null=True)
    github_id = models.CharField(max_length=255, blank=True, unique=True, null=True)
    github_username = models.CharField(max_length=255, blank=True)
    # ── Onboarding ────────────────────────────────────────────
    is_onboarded = models.BooleanField(default=False)
    onboarded_at = models.DateTimeField(null=True, blank=True)
    # ── Weekly digest preferences ─────────────────────────────
    digest_enabled = models.BooleanField(default=True)
    digest_day = models.CharField(
        max_length=10,
        default="monday",
        choices=[
            ("monday", "Monday"),
            ("tuesday", "Tuesday"),
            ("wednesday", "Wednesday"),
            ("thursday", "Thursday"),
            ("friday", "Friday"),
            ("saturday", "Saturday"),
            ("sunday", "Sunday"),
        ],
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        db_table = "users"
        ordering = ["-created_at"]

    def __str__(self):
        return self.email

    @property
    def is_premium(self):
        return self.role in [self.Role.PREMIUM, self.Role.ADMIN]

    @property
    def is_admin_user(self):
        return self.role == self.Role.ADMIN


class OnboardingPreferences(models.Model):
    """Stores user interest and use-case preferences captured during onboarding."""

    INTEREST_CHOICES = [
        ("ai_ml", "AI & Machine Learning"),
        ("web_dev", "Web Development"),
        ("security", "Security & Privacy"),
        ("cloud_devops", "Cloud & DevOps"),
        ("research", "Academic Research"),
        ("data_science", "Data Science"),
        ("open_source", "Open Source"),
        ("startup", "Startups & Business"),
        ("finance", "Finance & Crypto"),
        ("health_bio", "Health & Biotech"),
    ]

    USE_CASE_CHOICES = [
        ("research", "Daily Research Digest"),
        ("automation", "Workflow Automation"),
        ("learning", "Continuous Learning"),
        ("archiving", "Knowledge Archiving"),
        ("team", "Team Collaboration"),
    ]

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="onboarding_prefs"
    )
    interests = models.JSONField(
        default=list, blank=True, help_text="List of selected interest slugs"
    )
    use_case = models.CharField(max_length=20, choices=USE_CASE_CHOICES, blank=True)
    current_step = models.PositiveSmallIntegerField(default=1)
    completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "user_onboarding_preferences"

    def __str__(self):
        return f"OnboardingPrefs({self.user.email}, step={self.current_step}, done={self.completed})"
