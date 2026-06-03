"""
Migration: add Invoice model to billing app.

TASK-003-B1
"""
import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Invoice",
            fields=[
                ("id",               models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("stripe_invoice_id", models.CharField(max_length=100, unique=True, db_index=True)),
                ("amount_paid",       models.PositiveIntegerField(default=0, help_text="Amount in cents")),
                ("currency",          models.CharField(max_length=3, default="usd")),
                ("status",            models.CharField(max_length=30, default="paid")),
                ("pdf_url",           models.URLField(blank=True, max_length=500)),
                ("hosted_url",        models.URLField(blank=True, max_length=500)),
                ("period_start",      models.DateTimeField(null=True, blank=True)),
                ("period_end",        models.DateTimeField(null=True, blank=True)),
                ("created_at",        models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="invoices",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "billing_invoices",
                "verbose_name": "Invoice",
                "ordering": ["-created_at"],
            },
        ),
    ]
