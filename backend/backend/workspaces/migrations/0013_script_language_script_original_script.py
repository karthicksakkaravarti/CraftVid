# Generated by Django 5.0.11 on 2025-03-26 12:40

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("workspaces", "0012_alter_screen_output_file"),
    ]

    operations = [
        migrations.AddField(
            model_name="script",
            name="language",
            field=models.CharField(
                default="en",
                help_text="ISO language code",
                max_length=10,
                verbose_name="Language",
            ),
        ),
        migrations.AddField(
            model_name="script",
            name="original_script",
            field=models.ForeignKey(
                blank=True,
                help_text="The original script this is translated from",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="translations",
                to="workspaces.script",
            ),
        ),
    ]
