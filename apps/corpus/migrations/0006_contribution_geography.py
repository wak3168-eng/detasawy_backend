from django.db import migrations, models


def copy_profile_geography(apps, schema_editor):
    Contribution = apps.get_model("corpus", "Contribution")
    Profile = apps.get_model("identity", "Profile")
    profiles = {
        profile.user_id: profile
        for profile in Profile.objects.only("user_id", "country", "province", "district", "tehsil")
    }
    pending = []
    for contribution in Contribution.objects.all().iterator():
        profile = profiles.get(contribution.contributor_id)
        if profile is None:
            continue
        contribution.country = profile.country
        contribution.province = profile.province
        contribution.tehsil = profile.tehsil
        if contribution.district is None:
            contribution.district = profile.district
        pending.append(contribution)
        if len(pending) == 500:
            Contribution.objects.bulk_update(pending, ["country", "province", "district", "tehsil"])
            pending = []
    if pending:
        Contribution.objects.bulk_update(pending, ["country", "province", "district", "tehsil"])


class Migration(migrations.Migration):
    dependencies = [
        ("corpus", "0005_alter_prompt_kind"),
        ("identity", "0003_profile_photo_blob"),
    ]

    operations = [
        migrations.AddField("contribution", "country", models.JSONField(blank=True, null=True)),
        migrations.AddField("contribution", "province", models.JSONField(blank=True, null=True)),
        migrations.AddField("contribution", "tehsil", models.JSONField(blank=True, null=True)),
        migrations.RunPython(copy_profile_geography, migrations.RunPython.noop),
    ]
