from django.db import migrations


def seed_default_roles(apps, schema_editor):
    Role = apps.get_model("employees", "Role")
    defaults = [
        {
            "name": "CREATOR",
            "description": "Creates and edits tables in draft, then submits them for review.",
            "can_view": True,
            "can_create": True,
            "can_edit": True,
            "can_delete": False,
            "can_review": False,
            "can_approve": False,
        },
        {
            "name": "REVIEWER",
            "description": "Reviews submitted tables and passes them on or sends them back.",
            "can_view": True,
            "can_create": False,
            "can_edit": False,
            "can_delete": False,
            "can_review": True,
            "can_approve": False,
        },
        {
            "name": "APPROVER",
            "description": "Approves reviewed tables to confirm them.",
            "can_view": True,
            "can_create": False,
            "can_edit": False,
            "can_delete": False,
            "can_review": False,
            "can_approve": True,
        },
    ]
    for data in defaults:
        Role.objects.get_or_create(name=data["name"], defaults=data)


def remove_default_roles(apps, schema_editor):
    Role = apps.get_model("employees", "Role")
    Role.objects.filter(name__in=["CREATOR", "REVIEWER", "APPROVER"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("employees", "0002_role_employeeprofile_roles_roledepartment_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_default_roles, remove_default_roles),
    ]
