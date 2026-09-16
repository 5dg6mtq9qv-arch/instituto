from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("academico", "0052_alter_moodlecalificacion_options"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="claseasistencia",
            options={
                "ordering": ["clase", "estudiante__nombre"],
                "permissions": (("edit_closed_claseasistencia", "Puede editar asistencias cerradas"),),
            },
        ),
    ]
