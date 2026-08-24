import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("academico", "0010_materia_curso_horario_sql"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
                    name="Materia",
                    fields=[
                        ("id", models.BigAutoField(primary_key=True, serialize=False)),
                        ("nombre", models.CharField(max_length=150)),
                        ("nombre_corto", models.CharField(blank=True, max_length=50, null=True)),
                        ("descripcion", models.TextField(blank=True, null=True)),
                    ],
                    options={
                        "db_table": '"academico"."materia"',
                        "ordering": ["nombre"],
                    },
                ),
                migrations.CreateModel(
                    name="MateriaCurso",
                    fields=[
                        ("id", models.BigAutoField(primary_key=True, serialize=False)),
                        (
                            "materia",
                            models.ForeignKey(
                                db_column="id_materia",
                                on_delete=django.db.models.deletion.RESTRICT,
                                related_name="materia_cursos",
                                to="academico.materia",
                            ),
                        ),
                        (
                            "grupo",
                            models.ForeignKey(
                                db_column="id_grupo",
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="materia_cursos",
                                to="academico.curso",
                            ),
                        ),
                    ],
                    options={
                        "db_table": '"academico"."materia_curso"',
                        "ordering": ["grupo", "materia"],
                        "unique_together": {("materia", "grupo")},
                    },
                ),
                migrations.CreateModel(
                    name="MateriaHorario",
                    fields=[
                        ("id", models.BigAutoField(primary_key=True, serialize=False)),
                        (
                            "materia_grupo",
                            models.ForeignKey(
                                db_column="id_materia_grupo",
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="materia_horarios",
                                to="academico.materiacurso",
                            ),
                        ),
                        (
                            "horario_aula_curso",
                            models.ForeignKey(
                                db_column="id_horario_aula_curso",
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="materia_horarios",
                                to="academico.horarioaulacurso",
                            ),
                        ),
                    ],
                    options={
                        "db_table": '"academico"."materia_horario"',
                        "ordering": ["materia_grupo", "horario_aula_curso"],
                        "unique_together": {("materia_grupo", "horario_aula_curso")},
                    },
                ),
            ],
        ),
    ]
