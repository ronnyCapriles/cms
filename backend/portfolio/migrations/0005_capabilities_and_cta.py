"""Move the capability cards and the closing line out of the bundle.

Schema only — `0006` fills the new rows and columns with exactly what the
front end used to hard-code, so the page looks the same the moment this lands
and every word in it is editable afterwards.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('portfolio', '0004_metric_placement_dropped'),
    ]

    operations = [
        migrations.CreateModel(
            name='Capability',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('language', models.CharField(choices=[('en', 'English'), ('es', 'Español')], default='en', help_text='The language these fields are written in. Others go in Translations.', max_length=5)),
                ('title', models.CharField(help_text='e.g. Ingestion & CDC', max_length=120)),
                ('body', models.TextField(help_text='A sentence or two — it sits in a card.')),
                ('tools', models.CharField(blank=True, help_text='Comma separated, in the order they should read: Kafka, Debezium, Flink.', max_length=240)),
                ('order', models.IntegerField(default=0, help_text='Lower sorts first.')),
                ('published', models.BooleanField(default=True)),
            ],
            options={
                'verbose_name_plural': 'capabilities',
                'ordering': ['order', 'id'],
            },
        ),
        migrations.AddField(
            model_name='siteprofile',
            name='capabilities_kicker',
            field=models.CharField(blank=True, help_text='The small label beside it, e.g. 03 / Capabilities.', max_length=60),
        ),
        migrations.AddField(
            model_name='siteprofile',
            name='capabilities_title',
            field=models.CharField(blank=True, help_text='Heading over the capability cards. Blank keeps the built-in "What I run".', max_length=120),
        ),
        migrations.AddField(
            model_name='siteprofile',
            name='cta_headline',
            field=models.TextField(blank=True, help_text='The closing line above the contact buttons. A line break is a line break; wrap a word in *asterisks* to have it drawn as an outline.'),
        ),
    ]
