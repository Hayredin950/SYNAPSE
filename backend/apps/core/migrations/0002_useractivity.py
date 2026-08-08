import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial_bookmark_collection"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="UserActivity",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("content_type", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="contenttypes.contenttype")),
                ("object_id", models.CharField(max_length=50)),
                ("interaction_type", models.CharField(max_length=32, choices=[
                    ("view", "view"), ("bookmark", "bookmark"), ("unbookmark", "unbookmark"),
                    ("like", "like"), ("search", "search")
                ])),
                ("timestamp", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="activities", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": "user_activities",
                "ordering": ["-timestamp"],
            },
        ),
        migrations.AddIndex(
            model_name="useractivity",
            index=models.Index(fields=["user", "timestamp"], name="ua_user_time_idx"),
        ),
    ]
