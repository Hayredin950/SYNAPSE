# Generated migration — Phase 2.1 NLP Pipeline
# Adds nlp_processed boolean flag to Article model.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("articles", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="article",
            name="nlp_processed",
            field=models.BooleanField(
                default=False,
                help_text="True once the NLP pipeline (keywords, topic, sentiment) has run.",
                db_index=True,
            ),
        ),
    ]
