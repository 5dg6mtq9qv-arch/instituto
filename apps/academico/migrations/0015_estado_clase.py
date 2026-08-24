import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("academico", "0014_clase_sql"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
                    name="Clase",
                    fields=[
                        ("id", models.BigAutoField(primary_key=True, serialize=False)),
                        ("fecha", models.DateField()),
                        ("descripcion", models.TextField(blank=True, null=True)),
                        (
                            "horario_aula_curso",
                            models.ForeignKey(
                                db_column="id_horario_aula_curso",
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="clases",
                                to="academico.horarioaulacurso",
                            ),
                        ),
                        (
                            "materia_curso",
                            models.ForeignKey(
                                db_column="id_materia_curso",
                                on_delete=django.db.models.deletion.RESTRICT,
                                related_name="clases",
                                to="academico.materiacurso",
                            ),
                        ),
                    ],
                    options={
                        "db_table": '"academico"."clase"',
                        "ordering": ["fecha", "horario_aula_curso"],
                        "unique_together": {("horario_aula_curso", "fecha")},
                    },
                ),
            ],
        ),
    ]
