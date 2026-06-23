from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0002_ninverification'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='collectorprofile',
            name='review_notes',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='collectorprofile',
            name='reviewed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='collectorprofile',
            name='reviewed_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='collector_reviews',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
