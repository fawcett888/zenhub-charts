# -*- coding: utf-8 -*-
# Generated by Django 1.11.4 on 2017-08-15 14:07
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('issue_tracker', '0014_remove_pipeline_is_cycle_time_starter'),
    ]

    operations = [
        migrations.AlterField(
            model_name='pipeline',
            name='pipeline_id',
            field=models.CharField(max_length=255, unique=True),
        ),
    ]
