"""
Migration: Add onboarding fields, GitHub OAuth fields, digest prefs,
           and OnboardingPreferences model to the users app.
"""
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0002_add_email_verified_google_id'),
    ]

    operations = [
        # ── GitHub OAuth fields ──────────────────────────────────────────────
        migrations.AddField(
            model_name='user',
            name='github_id',
            field=models.CharField(blank=True, max_length=255, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='user',
            name='github_username',
            field=models.CharField(blank=True, max_length=255),
        ),
        # ── Onboarding fields ────────────────────────────────────────────────
        migrations.AddField(
            model_name='user',
            name='is_onboarded',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='user',
            name='onboarded_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        # ── Weekly digest preferences ────────────────────────────────────────
        migrations.AddField(
            model_name='user',
            name='digest_enabled',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='user',
            name='digest_day',
            field=models.CharField(
                choices=[
                    ('monday', 'Monday'), ('tuesday', 'Tuesday'),
                    ('wednesday', 'Wednesday'), ('thursday', 'Thursday'),
                    ('friday', 'Friday'), ('saturday', 'Saturday'),
                    ('sunday', 'Sunday'),
                ],
                default='monday',
                max_length=10,
            ),
        ),
        # ── OnboardingPreferences table ──────────────────────────────────────
        migrations.CreateModel(
            name='OnboardingPreferences',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('interests', models.JSONField(blank=True, default=list, help_text='List of selected interest slugs')),
                ('use_case', models.CharField(
                    blank=True, max_length=20,
                    choices=[
                        ('research', 'Daily Research Digest'),
                        ('automation', 'Workflow Automation'),
                        ('learning', 'Continuous Learning'),
                        ('archiving', 'Knowledge Archiving'),
                        ('team', 'Team Collaboration'),
                    ],
                )),
                ('current_step', models.PositiveSmallIntegerField(default=1)),
                ('completed', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='onboarding_prefs',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'db_table': 'user_onboarding_preferences'},
        ),
    ]
