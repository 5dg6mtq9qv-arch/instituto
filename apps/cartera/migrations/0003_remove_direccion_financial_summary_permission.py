from django.db import migrations


def remove_direccion_financial_summary_permission(apps, schema_editor):
    group_model = apps.get_model("auth", "Group")
    permission_model = apps.get_model("auth", "Permission")

    direccion = group_model.objects.filter(name="Direccion").first()
    permission = permission_model.objects.filter(
        content_type__app_label="cartera",
        codename="view_resumen_financiero",
    ).first()
    if direccion and permission:
        direccion.permissions.remove(permission)


class Migration(migrations.Migration):
    dependencies = [
        ("cartera", "0002_planpago_view_resumen_financiero"),
    ]

    operations = [
        migrations.RunPython(
            remove_direccion_financial_summary_permission,
            migrations.RunPython.noop,
        ),
    ]
