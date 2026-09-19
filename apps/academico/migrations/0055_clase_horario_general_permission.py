from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("academico", "0054_clase_asistencia_cierre_automatico"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="clase",
            options={
                "ordering": ["fecha", "horario_aula_curso"],
                "permissions": [("view_general_clase", "Puede ver el horario general")],
            },
        ),
    ]
