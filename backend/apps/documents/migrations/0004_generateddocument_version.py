import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('documents', '0003_alter_generateddocument_doc_type'),
    ]
    operations = [
        migrations.AddField(
            model_name='generateddocument',
            name='version',
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AddField(
            model_name='generateddocument',
            name='parent',
            field=models.ForeignKey(
                null=True, blank=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='versions',
                to='documents.generateddocument',
            ),
        ),
    ]
