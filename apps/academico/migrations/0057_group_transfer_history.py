from datetime import timedelta

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models
from django.db.models import Max, Min


def rebuild_overwritten_group_history(apps, schema_editor):
    ClaseAsistencia = apps.get_model("academico", "ClaseAsistencia")
    ClaseEstudianteMovimiento = apps.get_model("academico", "ClaseEstudianteMovimiento")
    CursoPeriodo = apps.get_model("academico", "CursoPeriodo")
    GrupoEstudiante = apps.get_model("academico", "GrupoEstudiante")
    GrupoEstudianteTraslado = apps.get_model("academico", "GrupoEstudianteTraslado")

    for current in GrupoEstudiante.objects.filter(estado="activo").iterator():
        attendance_groups = (
            ClaseAsistencia.objects.filter(estudiante_id=current.estudiante_id)
            .exclude(clase__materia_curso__grupo_id=current.grupo_id)
            .values("clase__materia_curso__grupo_id")
            .annotate(first_date=Min("clase__fecha"), last_date=Max("clase__fecha"))
        )
        movement_group_ids = set(
            ClaseEstudianteMovimiento.objects.filter(asignacion_id=current.pk).values_list(
                "clase_destino__materia_curso__grupo_id", flat=True
            )
        )
        for attendance_group in attendance_groups:
            previous_group_id = attendance_group["clase__materia_curso__grupo_id"]
            if previous_group_id in movement_group_ids:
                continue
            if current.periodo_id and not CursoPeriodo.objects.filter(
                curso_id=previous_group_id,
                periodo_id=current.periodo_id,
            ).exists():
                continue
            existing = GrupoEstudiante.objects.filter(
                ficha_inscripcion_id=current.ficha_inscripcion_id,
                periodo_id=current.periodo_id,
                grupo_id=previous_group_id,
            ).first()
            if existing:
                continue

            first_date = attendance_group["first_date"]
            created_date = current.created_at.date() if current.created_at else first_date
            start_date = min(first_date, created_date)
            expected_end = current.fecha_asignacion - timedelta(days=1)
            end_date = max(start_date, expected_end, attendance_group["last_date"])
            previous = GrupoEstudiante.objects.create(
                ficha_inscripcion_id=current.ficha_inscripcion_id,
                estudiante_id=current.estudiante_id,
                grupo_id=previous_group_id,
                periodo_id=current.periodo_id,
                fecha_asignacion=start_date,
                fecha_fin=end_date,
                estado="trasladado",
                observacion="Historial reconstruido a partir de asistencias registradas.",
                usuario_updated_id=current.usuario_updated_id,
            )
            GrupoEstudianteTraslado.objects.create(
                asignacion_origen_id=previous.pk,
                asignacion_destino_id=current.pk,
                fecha_traslado=current.fecha_asignacion,
                motivo="Historial reconstruido a partir de asistencias registradas.",
                usuario_id=current.usuario_updated_id,
            )


class Migration(migrations.Migration):
    dependencies = [
        ("academico", "0056_clase_informe_mensual_docente_permission"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        'DROP INDEX IF EXISTS "academico".'
                        '"uq_grupo_estudiante_ficha_periodo";'
                    ),
                    reverse_sql=(
                        'CREATE UNIQUE INDEX "uq_grupo_estudiante_ficha_periodo" '
                        'ON "academico"."grupo_estudiante" '
                        '("id_ficha_inscripcion", "id_periodo") '
                        'WHERE "id_periodo" IS NOT NULL;'
                    ),
                ),
            ],
            state_operations=[
                migrations.RemoveConstraint(
                    model_name="grupoestudiante",
                    name="uq_grupo_estudiante_ficha_periodo",
                ),
            ],
        ),
        migrations.AlterField(
            model_name="grupoestudiante",
            name="estado",
            field=models.CharField(
                choices=[
                    ("activo", "Activo"),
                    ("finalizado", "Finalizado"),
                    ("retirado", "Retirado"),
                    ("trasladado", "Trasladado"),
                ],
                default="activo",
                max_length=20,
            ),
        ),
        migrations.AddConstraint(
            model_name="grupoestudiante",
            constraint=models.UniqueConstraint(
                condition=models.Q(periodo__isnull=False, estado="activo"),
                fields=("ficha_inscripcion", "periodo"),
                name="uq_grupo_estudiante_activo_periodo",
            ),
        ),
        migrations.AddConstraint(
            model_name="grupoestudiante",
            constraint=models.UniqueConstraint(
                condition=models.Q(periodo__isnull=True, estado="activo"),
                fields=("ficha_inscripcion",),
                name="uq_grupo_estudiante_activo_sin_periodo",
            ),
        ),
        migrations.CreateModel(
            name="GrupoEstudianteTraslado",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("fecha_traslado", models.DateField(default=django.utils.timezone.localdate)),
                ("motivo", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "asignacion_destino",
                    models.ForeignKey(
                        db_column="id_asignacion_destino",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="traslados_entrada",
                        to="academico.grupoestudiante",
                    ),
                ),
                (
                    "asignacion_origen",
                    models.ForeignKey(
                        db_column="id_asignacion_origen",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="traslados_salida",
                        to="academico.grupoestudiante",
                    ),
                ),
                (
                    "usuario",
                    models.ForeignKey(
                        blank=True,
                        db_column="id_usuario",
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="traslados_grupo_estudiante",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": '"academico"."grupo_estudiante_traslado"',
                "ordering": ["-fecha_traslado", "-created_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="grupoestudiantetraslado",
            constraint=models.UniqueConstraint(
                fields=("asignacion_origen", "asignacion_destino"),
                name="uq_grupo_estudiante_traslado",
            ),
        ),
        migrations.RunPython(rebuild_overwritten_group_history, migrations.RunPython.noop),
    ]
