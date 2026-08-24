import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("academico", "0018_profesor_materia_curso_sql"),
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
                    name="ProfesorMateriaCurso",
                    fields=[
                        ("id", models.BigAutoField(primary_key=True, serialize=False)),
                        (
                            "partner",
                            models.ForeignKey(
                                db_column="id_partner",
                                on_delete=django.db.models.deletion.RESTRICT,
                                related_name="profesor_materia_cursos",
                                to="core.partner",
                            ),
                        ),
                        (
                            "materia_curso",
                            models.ForeignKey(
                                db_column="id_materia_curso",
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="profesor_materia_cursos",
                                to="academico.materiacurso",
                            ),
                        ),
                    ],
                    options={
                        "db_table": '"academico"."profesor_materia_curso"',
                        "ordering": ["materia_curso", "partner"],
                        "unique_together": {("partner", "materia_curso")},
                    },
                ),
            ],
        ),
    ]
