from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("academico", "0055_clase_horario_general_permission"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="clase",
            options={
                "ordering": ["fecha", "horario_aula_curso"],
                "permissions": [
                    ("view_general_clase", "Puede ver el horario general"),
                    (
                        "view_informe_mensual_docente_clase",
                        "Puede ver el informe mensual docente",
                    ),
                ],
            },
        ),
    ]
