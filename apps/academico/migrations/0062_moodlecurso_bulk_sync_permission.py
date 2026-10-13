from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("academico", "0061_horarioaulacursoexclusion"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="moodlecurso",
            options={
                "default_permissions": (),
                "permissions": (
                    (
                        "crear_moodlecurso",
                        "Crear curso en Moodle con docentes y alumnos",
                    ),
                    (
                        "sincronizar_todos_moodlecurso",
                        "Sincronizar todos los cursos con Moodle",
                    ),
                ),
            },
        ),
    ]
