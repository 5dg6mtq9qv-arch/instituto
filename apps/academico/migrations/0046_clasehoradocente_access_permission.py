from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("academico", "0045_clasetema_clase_temas"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="clasehoradocente",
            options={
                "ordering": ["clase"],
                "permissions": (
                    ("access_clasehoradocente", "Puede acceder a horas docente"),
                    ("report_clasehoradocente", "Puede ver reporte de horas docente"),
                ),
            },
        ),
    ]
