"""
Initial migration for Organizations app — TASK-006.
Creates: organizations, organization_memberships, organization_invites tables.
"""
import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ── Organization ────────────────────────────────────────────────────
        migrations.CreateModel(
            name="Organization",
            fields=[
                ("id",          models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name",        models.CharField(max_length=100)),
                ("slug",        models.SlugField(max_length=110, unique=True)),
                ("description", models.TextField(blank=True, max_length=500)),
                ("logo_url",    models.URLField(blank=True, max_length=500)),
                ("website",     models.URLField(blank=True, max_length=500)),
                ("plan",        models.CharField(
                    choices=[("free", "Free"), ("pro", "Pro"), ("enterprise", "Enterprise")],
                    default="free",
                    max_length=20,
                )),
                ("owner", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="owned_organizations",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("created_at",  models.DateTimeField(auto_now_add=True)),
                ("updated_at",  models.DateTimeField(auto_now=True)),
            ],
            options={"db_table": "organizations", "ordering": ["-created_at"]},
        ),

        # ── Membership ──────────────────────────────────────────────────────
        migrations.CreateModel(
            name="Membership",
            fields=[
                ("id",        models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("role",      models.CharField(
                    choices=[("owner", "Owner"), ("admin", "Admin"), ("member", "Member"), ("viewer", "Viewer")],
                    default="member",
                    max_length=20,
                )),
                ("is_active",  models.BooleanField(default=True)),
                ("joined_at",  models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="memberships",
                    to="organizations.organization",
                )),
                ("user", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="org_memberships",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                "db_table": "organization_memberships",
                "ordering": ["joined_at"],
                "unique_together": {("organization", "user")},
            },
        ),

        # ── OrganizationInvite ──────────────────────────────────────────────
        migrations.CreateModel(
            name="OrganizationInvite",
            fields=[
                ("id",          models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("email",       models.EmailField(db_index=True)),
                ("role",        models.CharField(
                    choices=[("owner", "Owner"), ("admin", "Admin"), ("member", "Member"), ("viewer", "Viewer")],
                    default="member",
                    max_length=20,
                )),
                ("token",       models.UUIDField(default=uuid.uuid4, unique=True)),
                ("is_accepted", models.BooleanField(default=False)),
                ("accepted_at", models.DateTimeField(blank=True, null=True)),
                ("expires_at",  models.DateTimeField(blank=True, null=True)),
                ("created_at",  models.DateTimeField(auto_now_add=True)),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="invites",
                    to="organizations.organization",
                )),
                ("invited_by", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="sent_org_invites",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={"db_table": "organization_invites", "ordering": ["-created_at"]},
        ),
    ]
