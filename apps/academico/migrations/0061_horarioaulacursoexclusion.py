from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("academico", "0060_clase_delete_scheduled_permission"),
    ]

    operations = [
        migrations.CreateModel(
            name="HorarioAulaCursoExclusion",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("fecha", models.DateField()),
                (
                    "horario_aula_curso",
                    models.ForeignKey(
                        db_column="id_horario_aula_curso",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="exclusiones",
                        to="academico.horarioaulacurso",
                    ),
                ),
            ],
            options={
                "db_table": '"academico"."horario_aula_curso_exclusion"',
                "ordering": ["horario_aula_curso", "fecha"],
            },
        ),
        migrations.AddConstraint(
            model_name="horarioaulacursoexclusion",
            constraint=models.UniqueConstraint(
                fields=("horario_aula_curso", "fecha"),
                name="uq_horario_aula_curso_exclusion_fecha",
            ),
        ),
    ]
