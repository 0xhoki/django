# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2017-05-21 10:09
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('accounts', '0002_account_plan'),
        ('contenttypes', '0002_remove_content_type_name'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='RecentActivity',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('object_id', models.PositiveIntegerField()),
                ('action_flag', models.PositiveSmallIntegerField(choices=[(1, b'New'), (2, b'Updated')], verbose_name='action flag')),
                ('action_time', models.DateTimeField(auto_now_add=True)),
                ('account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='recent_activity', to='accounts.Account')),
                ('content_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='contenttypes.ContentType')),
                ('init_user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='recent_activity', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-action_time'],
                'verbose_name': 'Recent Activity',
                'verbose_name_plural': 'Recent Activities',
            },
        ),
    ]