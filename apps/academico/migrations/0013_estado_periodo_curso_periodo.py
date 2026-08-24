import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("academico", "0012_periodo_curso_periodo_sql"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
                    name="Periodo",
                    fields=[
                        ("id", models.BigAutoField(primary_key=True, serialize=False)),
                        ("nombre", models.CharField(max_length=150)),
                        ("fecha_inicio", models.DateField()),
                        ("fecha_fin", models.DateField()),
                    ],
                    options={
                        "db_table": '"academico"."periodo"',
                        "ordering": ["-fecha_inicio", "nombre"],
                        "constraints": [
                            models.CheckConstraint(
                                condition=models.Q(("fecha_fin__gte", models.F("fecha_inicio"))),
                                name="chk_periodo_fechas",
                            )
                        ],
                    },
                ),
                migrations.CreateModel(
                    name="CursoPeriodo",
                    fields=[
                        ("id", models.BigAutoField(primary_key=True, serialize=False)),
                        (
                            "curso",
                            models.ForeignKey(
                                db_column="id_curso",
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="curso_periodos",
                                to="academico.curso",
                            ),
                        ),
                        (
                            "periodo",
                            models.ForeignKey(
                                db_column="id_periodo",
                                on_delete=django.db.models.deletion.RESTRICT,
                                related_name="curso_periodos",
                                to="academico.periodo",
                            ),
                        ),
                    ],
                    options={
                        "db_table": '"academico"."curso_periodo"',
                        "ordering": ["periodo", "curso"],
                        "unique_together": {("curso", "periodo")},
                    },
                ),
            ],
        ),
    ]
