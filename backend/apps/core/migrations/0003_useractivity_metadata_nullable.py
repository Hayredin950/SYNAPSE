import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0002_useractivity"),
    ]

    operations = [
        migrations.AlterField(
            model_name='useractivity',
            name='content_type',
            field=models.ForeignKey(null=True, blank=True, on_delete=django.db.models.deletion.CASCADE, to='contenttypes.contenttype'),
        ),
        migrations.AlterField(
            model_name='useractivity',
            name='object_id',
            field=models.CharField(max_length=50, null=True, blank=True),
        ),
        migrations.AddField(
            model_name='useractivity',
            name='metadata',
            field=models.JSONField(default=dict, blank=True),
        ),
    ]
