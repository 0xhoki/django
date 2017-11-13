# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2017-04-09 09:19
from __future__ import unicode_literals

import datetime
from django.conf import settings
import django.core.files.storage
from django.db import migrations, models
import django.db.models.deletion
from django.utils.timezone import utc
import mptt.fields


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('meetings', '0001_initial'),
        ('accounts', '0002_account_plan'),
        ('profiles', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('committees', '0002_committee_chairman'),
    ]

    operations = [
        migrations.CreateModel(
            name='AuditTrail',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(blank=True, max_length=250, verbose_name='name')),
                ('file', models.FileField(storage=django.core.files.storage.FileSystemStorage(), upload_to=b'uploads/docs/%Y%m%d', verbose_name='file')),
                ('pdf_preview', models.FileField(blank=True, null=True, storage=django.core.files.storage.FileSystemStorage(), upload_to=b'uploads/docs/%Y%m%d', verbose_name='pdf_preview')),
                ('type', models.PositiveIntegerField(choices=[(1, 'agenda'), (2, 'minutes'), (3, 'other')], default=3, verbose_name='document type')),
                ('created_at', models.DateTimeField(default=datetime.datetime(2017, 4, 9, 9, 19, 58, 86662, tzinfo=utc), verbose_name='upload date')),
                ('change_type', models.PositiveIntegerField(choices=[(0, 'update'), (1, 'deleted')], default=0, verbose_name='type of changes')),
                ('latest_version', models.PositiveIntegerField(blank=True, null=True)),
                ('revision', models.PositiveIntegerField(blank=True, null=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='audits', to=settings.AUTH_USER_MODEL, verbose_name='user')),
            ],
        ),
        migrations.CreateModel(
            name='Document',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(blank=True, max_length=250, verbose_name='name')),
                ('file', models.FileField(storage=django.core.files.storage.FileSystemStorage(), upload_to=b'uploads/docs/%Y%m%d', verbose_name='file')),
                ('pdf_preview', models.FileField(blank=True, null=True, storage=django.core.files.storage.FileSystemStorage(), upload_to=b'uploads/docs/%Y%m%d', verbose_name='pdf_preview')),
                ('type', models.PositiveIntegerField(choices=[(1, 'agenda'), (2, 'minutes'), (3, 'other')], default=3, verbose_name='document type')),
                ('created_at', models.DateTimeField(default=datetime.datetime(2017, 4, 9, 9, 19, 58, 86662, tzinfo=utc), verbose_name='upload date')),
                ('previous_version', models.PositiveIntegerField(blank=True, null=True)),
                ('account', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='documents', to='accounts.Account', verbose_name='account')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Folder',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, verbose_name='name')),
                ('slug', models.SlugField(unique=True, verbose_name='slug')),
                ('created', models.DateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', models.DateTimeField(auto_now=True, verbose_name='modified')),
                ('protected', models.BooleanField(default=False, help_text='For special folders like "Trash"', verbose_name='protected')),
                ('lft', models.PositiveIntegerField(db_index=True, editable=False)),
                ('rght', models.PositiveIntegerField(db_index=True, editable=False)),
                ('tree_id', models.PositiveIntegerField(db_index=True, editable=False)),
                ('level', models.PositiveIntegerField(db_index=True, editable=False)),
                ('account', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='folders', to='accounts.Account', verbose_name='account')),
                ('committee', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='folder', to='committees.Committee', verbose_name='committee')),
                ('meeting', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='folder', to='meetings.Meeting', verbose_name='meeting')),
                ('membership', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='private_folder', to='profiles.Membership', verbose_name='membership')),
                ('parent', mptt.fields.TreeForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='children', to='documents.Folder', verbose_name='parent')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='folders', to=settings.AUTH_USER_MODEL, verbose_name='user')),
            ],
            options={
                'ordering': ('name',),
                'verbose_name': 'folder',
                'verbose_name_plural': 'folders',
            },
        ),
        migrations.AddField(
            model_name='document',
            name='folder',
            field=mptt.fields.TreeForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='documents', to='documents.Folder', verbose_name='folder'),
        ),
        migrations.AddField(
            model_name='document',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='documents', to=settings.AUTH_USER_MODEL, verbose_name='user'),
        ),
        migrations.AlterUniqueTogether(
            name='folder',
            unique_together=set([('parent', 'name')]),
        ),
        migrations.AlterUniqueTogether(
            name='audittrail',
            unique_together=set([('latest_version', 'revision')]),
        ),
    ]