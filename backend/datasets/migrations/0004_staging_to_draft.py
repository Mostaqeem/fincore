from django.db import migrations


def staging_to_draft(apps, schema_editor):
    Dataset = apps.get_model("datasets", "Dataset")
    Dataset.objects.filter(status="staging").update(status="draft")


def draft_to_staging(apps, schema_editor):
    Dataset = apps.get_model("datasets", "Dataset")
    Dataset.objects.filter(status="draft").update(status="staging")


class Migration(migrations.Migration):

    dependencies = [
        ("datasets", "0003_dataset_approval_comment_dataset_approved_at_and_more"),
    ]

    operations = [
        migrations.RunPython(staging_to_draft, draft_to_staging),
    ]
