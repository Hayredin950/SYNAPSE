from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0006_generateddocument_organization'),
    ]

    operations = [
        migrations.AddField(
            model_name='generateddocument',
            name='sources_metadata',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='List of Synapse sources (articles/papers/repos/videos) used as RAG context.',
            ),
        ),
    ]
