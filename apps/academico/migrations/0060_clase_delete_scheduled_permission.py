from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("academico", "0059_moodlecuenta_suspend_inactive_permission"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="clase",
            options={
                "ordering": ["fecha", "horario_aula_curso"],
                "permissions": [
                    (
                        "delete_scheduled_clase",
                        "Puede eliminar una clase del horario y sus datos relacionados",
                    ),
                    ("view_general_clase", "Puede ver el horario general"),
                    (
                        "view_informe_mensual_docente_clase",
                        "Puede ver el informe mensual docente",
                    ),
                ],
            },
        ),
    ]
