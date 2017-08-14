# -*- coding: utf-8 -*-
# Generated by Django 1.11.4 on 2017-08-07 14:58
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('issue_tracker', '0003_auto_20170807_1100'),
    ]

    operations = [
        migrations.AddField(
            model_name='duration',
            name='latest_transfer',
            field=models.ForeignKey(default=None, on_delete=django.db.models.deletion.CASCADE, related_name='durations', to='issue_tracker.Transfer'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='pipeline',
            name='order',
            field=models.PositiveSmallIntegerField(default=None),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='pipeline',
            name='repo',
            field=models.ForeignKey(default=None, on_delete=django.db.models.deletion.CASCADE, to='issue_tracker.Repo'),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='pipeline',
            name='name',
            field=models.CharField(max_length=255),
        ),
        migrations.AlterUniqueTogether(
            name='pipeline',
            unique_together=set([('name', 'repo')]),
        ),
    ]