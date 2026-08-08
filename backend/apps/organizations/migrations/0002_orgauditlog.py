"""
TASK-006-B5: Add OrgAuditLog model.
"""
import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('organizations', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='OrgAuditLog',
            fields=[
                ('id',          models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('action',      models.CharField(
                    choices=[
                        ('org_created',      'Org Created'),
                        ('org_deleted',      'Org Deleted'),
                        ('settings_changed', 'Settings Changed'),
                        ('member_added',     'Member Added'),
                        ('member_removed',   'Member Removed'),
                        ('role_changed',     'Role Changed'),
                        ('invite_sent',      'Invite Sent'),
                        ('invite_cancelled', 'Invite Cancelled'),
                        ('invite_accepted',  'Invite Accepted'),
                    ],
                    db_index=True,
                    max_length=30,
                )),
                ('resource',    models.CharField(blank=True, max_length=255)),
                ('metadata',    models.JSONField(blank=True, default=dict)),
                ('ip_address',  models.GenericIPAddressField(blank=True, null=True)),
                ('timestamp',   models.DateTimeField(auto_now_add=True, db_index=True)),
                ('organization', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='audit_logs',
                    to='organizations.organization',
                )),
                ('actor', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='org_audit_actions',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'db_table': 'org_audit_logs', 'ordering': ['-timestamp']},
        ),
    ]
