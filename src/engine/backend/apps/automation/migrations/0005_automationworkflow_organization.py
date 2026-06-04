"""
TASK-006-B4: Add nullable organization FK to AutomationWorkflow.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('automation', '0004_workflowrun_celery_task_id_event_config'),
        ('organizations', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='automationworkflow',
            name='organization',
            field=models.ForeignKey(
                blank=True,
                help_text='If set, this workflow belongs to an org workspace.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='workflows',
                to='organizations.organization',
            ),
        ),
    ]
