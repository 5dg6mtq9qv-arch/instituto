import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("academico", "0008_distribucion_grupos_cursos"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
                    name="Aula",
                    fields=[
                        ("id", models.BigAutoField(primary_key=True, serialize=False)),
                        ("nombre", models.CharField(max_length=100)),
                        ("descripcion", models.TextField(blank=True, null=True)),
                    ],
                    options={
                        "db_table": '"academico"."aula"',
                        "ordering": ["nombre"],
                    },
                ),
                migrations.CreateModel(
                    name="Dia",
                    fields=[
                        ("id", models.BigAutoField(primary_key=True, serialize=False)),
                        ("dia", models.CharField(max_length=20, unique=True)),
                    ],
                    options={
                        "db_table": '"academico"."dia"',
                        "ordering": ["id"],
                    },
                ),
                migrations.CreateModel(
                    name="Curso",
                    fields=[
                        ("id", models.BigAutoField(primary_key=True, serialize=False)),
                        ("nombre", models.CharField(max_length=150)),
                        ("activo", models.BooleanField(default=True)),
                        ("descripcion", models.TextField(blank=True, null=True)),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        ("updated_at", models.DateTimeField(auto_now=True)),
                        (
                            "usuario_updated",
                            models.ForeignKey(
                                blank=True,
                                db_column="id_usuario_updated",
                                null=True,
                                on_delete=django.db.models.deletion.DO_NOTHING,
                                related_name="academico_cursos_actualizados",
                                to=settings.AUTH_USER_MODEL,
                            ),
                        ),
                    ],
                    options={
                        "db_table": '"academico"."curso"',
                        "ordering": ["nombre"],
                    },
                ),
                migrations.CreateModel(
                    name="AulaCurso",
                    fields=[
                        ("id", models.BigAutoField(primary_key=True, serialize=False)),
                        ("nombre", models.CharField(blank=True, max_length=150, null=True)),
                        ("descripcion", models.TextField(blank=True, null=True)),
                        (
                            "aula",
                            models.ForeignKey(
                                db_column="id_aula",
                                on_delete=django.db.models.deletion.RESTRICT,
                                related_name="aula_cursos",
                                to="academico.aula",
                            ),
                        ),
                        (
                            "curso",
                            models.ForeignKey(
                                db_column="id_curso",
                                on_delete=django.db.models.deletion.RESTRICT,
                                related_name="aula_cursos",
                                to="academico.curso",
                            ),
                        ),
                    ],
                    options={
                        "db_table": '"academico"."aula_curso"',
                        "ordering": ["aula", "curso"],
                        "unique_together": {("aula", "curso")},
                    },
                ),
                migrations.CreateModel(
                    name="Horario",
                    fields=[
                        ("id", models.BigAutoField(primary_key=True, serialize=False)),
                        ("hora_inicio", models.TimeField()),
                        ("hora_fin", models.TimeField()),
                    ],
                    options={
                        "db_table": '"academico"."horario"',
                        "ordering": ["hora_inicio", "hora_fin"],
                        "constraints": [
                            models.CheckConstraint(
                                condition=models.Q(("hora_fin__gt", models.F("hora_inicio"))),
                                name="chk_horario_horas",
                            )
                        ],
                    },
                ),
                migrations.CreateModel(
                    name="HorarioDia",
                    fields=[
                        ("id", models.BigAutoField(primary_key=True, serialize=False)),
                        (
                            "dia",
                            models.ForeignKey(
                                db_column="id_dia",
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="horario_dias",
                                to="academico.dia",
                            ),
                        ),
                        (
                            "horario",
                            models.ForeignKey(
                                db_column="id_horario",
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="horario_dias",
                                to="academico.horario",
                            ),
                        ),
                    ],
                    options={
                        "db_table": '"academico"."horario_dia"',
                        "ordering": ["dia", "horario"],
                        "unique_together": {("dia", "horario")},
                    },
                ),
                migrations.CreateModel(
                    name="HorarioAulaCurso",
                    fields=[
                        ("id", models.BigAutoField(primary_key=True, serialize=False)),
                        (
                            "aula_curso",
                            models.ForeignKey(
                                db_column="id_aula_curso",
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="horario_aula_cursos",
                                to="academico.aulacurso",
                            ),
                        ),
                        (
                            "horario_dia",
                            models.ForeignKey(
                                db_column="id_horario_dia",
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="horario_aula_cursos",
                                to="academico.horariodia",
                            ),
                        ),
                    ],
                    options={
                        "db_table": '"academico"."horario_aula_curso"',
                        "ordering": ["aula_curso", "horario_dia"],
                        "unique_together": {("aula_curso", "horario_dia")},
                    },
                ),
            ],
        ),
    ]
