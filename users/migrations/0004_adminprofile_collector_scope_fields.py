from collections import Counter

from django.db import migrations, models
import django.db.models.deletion


def _parse_request_notes(value):
    parsed = {'lga': '', 'area': ''}
    for line in str(value or '').splitlines():
        line = line.strip()
        if line.startswith('LGA:'):
            parsed['lga'] = line.replace('LGA:', '', 1).strip()
        if line.startswith('Area:'):
            parsed['area'] = line.replace('Area:', '', 1).strip()
    return parsed


def backfill_scope_fields(apps, schema_editor):
    from users.location_scope import resolve_lga

    User = apps.get_model('users', 'User')
    CollectorProfile = apps.get_model('users', 'CollectorProfile')
    AdminProfile = apps.get_model('users', 'AdminProfile')
    PickupRequest = apps.get_model('pickups', 'PickupRequest')
    Job = apps.get_model('pickups', 'Job')

    for profile in CollectorProfile.objects.all():
        area = (profile.area or '').strip() or (profile.service_area or '').strip()
        lga = (profile.lga or '').strip() or resolve_lga(area=area, service_area=profile.service_area)
        state = (profile.state or '').strip() or ('Lagos' if (area or lga) else '')
        updates = []
        if profile.area != area:
            profile.area = area
            updates.append('area')
        if profile.lga != lga:
            profile.lga = lga
            updates.append('lga')
        if profile.state != state:
            profile.state = state
            updates.append('state')
        if updates:
            profile.save(update_fields=updates)

    for admin in User.objects.filter(role='ADMIN'):
        if AdminProfile.objects.filter(user_id=admin.id).exists():
            continue

        counts = Counter()
        labels = {}

        for pickup in PickupRequest.objects.filter(logged_by_admin_id=admin.id).only('notes'):
            parsed = _parse_request_notes(pickup.notes)
            lga = resolve_lga(lga=parsed.get('lga'), area=parsed.get('area'))
            if lga:
                counts[lga.lower()] += 1
                labels.setdefault(lga.lower(), lga)

        for job in Job.objects.filter(assigned_by_id=admin.id).select_related('request'):
            parsed = _parse_request_notes(job.request.notes)
            lga = resolve_lga(lga=parsed.get('lga'), area=parsed.get('area'))
            if lga:
                counts[lga.lower()] += 1
                labels.setdefault(lga.lower(), lga)

        for profile in CollectorProfile.objects.filter(reviewed_by_id=admin.id):
            lga = resolve_lga(lga=profile.lga, area=profile.area, service_area=profile.service_area)
            if lga:
                counts[lga.lower()] += 1
                labels.setdefault(lga.lower(), lga)

        if not counts:
            continue

        normalized_lga = counts.most_common(1)[0][0]
        AdminProfile.objects.create(
            user_id=admin.id,
            state='Lagos',
            lga=labels[normalized_lga],
            area='',
        )


class Migration(migrations.Migration):

    dependencies = [
        ('pickups', '0001_initial'),
        ('users', '0003_collectorprofile_review_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='collectorprofile',
            name='area',
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name='collectorprofile',
            name='lga',
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name='collectorprofile',
            name='state',
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.CreateModel(
            name='AdminProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('state', models.CharField(max_length=120)),
                ('lga', models.CharField(max_length=120)),
                ('area', models.CharField(blank=True, max_length=120)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='admin_profile', to='users.user')),
            ],
        ),
        migrations.RunPython(backfill_scope_fields, migrations.RunPython.noop),
    ]
