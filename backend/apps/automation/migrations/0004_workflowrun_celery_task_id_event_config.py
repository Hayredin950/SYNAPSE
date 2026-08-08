from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('automation', '0003_add_workflow_status_field'),
    ]

    operations = [
        # Add event_config to AutomationWorkflow
        migrations.AddField(
            model_name='automationworkflow',
            name='event_config',
            field=models.JSONField(blank=True, default=dict),
        ),
        # Add celery_task_id to WorkflowRun for live status tracking
        migrations.AddField(
            model_name='workflowrun',
            name='celery_task_id',
            field=models.CharField(blank=True, db_index=True, default='', max_length=255),
            preserve_default=False,
        ),
        # Add trigger_event payload to WorkflowRun
        migrations.AddField(
            model_name='workflowrun',
            name='trigger_event',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
