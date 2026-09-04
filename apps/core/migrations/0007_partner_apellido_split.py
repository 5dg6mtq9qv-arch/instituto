from django.db import migrations, models


def split_full_name(value):
    parts = str(value or "").split()
    if len(parts) >= 4:
        return " ".join(parts[:-2]), " ".join(parts[-2:])
    if len(parts) >= 2:
        return " ".join(parts[:-1]), parts[-1]
    return str(value or "").strip(), ""


def split_partner_names(apps, schema_editor):
    Partner = apps.get_model("core", "Partner")
    for partner in Partner.objects.filter(apellido="").iterator():
        nombre, apellido = split_full_name(partner.nombre)
        if nombre != partner.nombre or apellido:
            partner.nombre = nombre
            partner.apellido = apellido
            partner.save(update_fields=["nombre", "apellido"])


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0006_partner_es_de_ibarra"),
    ]

    operations = [
        migrations.AddField(
            model_name="partner",
            name="apellido",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.RunPython(split_partner_names, migrations.RunPython.noop),
    ]
