"""
TASK-006-B4: Add nullable organization FK to GeneratedDocument.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0005_alter_generateddocument_doc_type'),
        ('organizations', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='generateddocument',
            name='organization',
            field=models.ForeignKey(
                blank=True,
                help_text='If set, this document belongs to an org workspace.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='documents',
                to='organizations.organization',
            ),
        ),
    ]
