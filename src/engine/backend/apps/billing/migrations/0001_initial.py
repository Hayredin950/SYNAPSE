"""
Initial migration for apps.billing — Subscription, ReferralCode, ReferralUse, UserFeedback.

Phase 9.3 — Growth & Iteration
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
        migrations.CreateModel(
            name="Subscription",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("plan", models.CharField(choices=[("free","Free"),("pro","Pro ($19/mo)"),("enterprise","Enterprise ($99/mo)")], default="free", max_length=20)),
                ("status", models.CharField(choices=[("active","Active"),("trialing","Trialing"),("past_due","Past Due"),("canceled","Canceled"),("incomplete","Incomplete"),("incomplete_expired","Incomplete Expired"),("unpaid","Unpaid")], default="active", max_length=30)),
                ("stripe_customer_id", models.CharField(blank=True, db_index=True, max_length=100)),
                ("stripe_subscription_id", models.CharField(blank=True, db_index=True, max_length=100)),
                ("stripe_price_id", models.CharField(blank=True, max_length=100)),
                ("current_period_start", models.DateTimeField(blank=True, null=True)),
                ("current_period_end", models.DateTimeField(blank=True, null=True)),
                ("cancel_at_period_end", models.BooleanField(default=False)),
                ("trial_end", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="subscription", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "billing_subscriptions", "verbose_name": "Subscription"},
        ),
        migrations.CreateModel(
            name="ReferralCode",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("code", models.CharField(db_index=True, max_length=12, unique=True)),
                ("uses", models.PositiveIntegerField(default=0)),
                ("max_uses", models.PositiveIntegerField(default=100)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("owner", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="referral_code", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "billing_referral_codes", "verbose_name": "Referral Code"},
        ),
        migrations.CreateModel(
            name="ReferralUse",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("reward_given", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("code", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="referral_uses", to="billing.referralcode")),
                ("referee", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="referred_by", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "billing_referral_uses", "verbose_name": "Referral Use"},
        ),
        migrations.CreateModel(
            name="UserFeedback",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("type", models.CharField(choices=[("nps","NPS Score"),("bug","Bug Report"),("feature","Feature Request"),("general","General Feedback")], default="general", max_length=20)),
                ("nps_score", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("message", models.TextField(blank=True, max_length=2000)),
                ("page_url", models.URLField(blank=True, max_length=500)),
                ("user_agent", models.CharField(blank=True, max_length=300)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="feedback", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "billing_user_feedback", "verbose_name": "User Feedback", "ordering": ["-created_at"]},
        ),
    ]
