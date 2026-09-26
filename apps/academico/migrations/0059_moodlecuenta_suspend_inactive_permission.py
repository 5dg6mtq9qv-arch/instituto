from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("academico", "0058_claseestrategiaorden"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="moodlecuenta",
            options={
                "default_permissions": (),
                "permissions": (
                    (
                        "exportar_moodlecuenta",
                        "Descargar Excel de accesos iniciales Moodle",
                    ),
                    (
                        "suspender_inactivos_moodlecuenta",
                        "Puede suspender estudiantes inactivos en Moodle",
                    ),
                ),
            },
        ),
    ]
