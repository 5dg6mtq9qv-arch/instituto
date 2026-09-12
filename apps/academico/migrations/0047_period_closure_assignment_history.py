from django.db import migrations, models
import django.db.models.deletion


def populate_assignment_periods(apps, schema_editor):
    GrupoEstudiante = apps.get_model("academico", "GrupoEstudiante")
    CursoPeriodo = apps.get_model("academico", "CursoPeriodo")
    periods_by_group = {}
    for link in CursoPeriodo.objects.order_by("curso_id", "-periodo__fecha_inicio", "-pk"):
        periods_by_group.setdefault(link.curso_id, link.periodo_id)
    for assignment in GrupoEstudiante.objects.filter(periodo__isnull=True).iterator():
        period_id = periods_by_group.get(assignment.grupo_id)
        if period_id:
            assignment.periodo_id = period_id
            assignment.save(update_fields=["periodo"])


class Migration(migrations.Migration):
    dependencies = [
        ("academico", "0046_clasehoradocente_access_permission"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="grupoestudiante",
            options={"ordering": ["periodo", "grupo", "estudiante__apellido", "estudiante__nombre"]},
        ),
        migrations.AddField(
            model_name="periodo",
            name="estado",
            field=models.CharField(
                choices=[("activo", "Activo"), ("cerrado", "Cerrado")],
                default="activo",
                max_length=20,
            ),
        ),
        migrations.RunSQL(
            sql=(
                'ALTER TABLE "academico"."grupo_estudiante" '
                'DROP CONSTRAINT IF EXISTS "grupo_estudiante_id_ficha_inscripcion_key";'
            ),
            reverse_sql=(
                'ALTER TABLE "academico"."grupo_estudiante" '
                'ADD CONSTRAINT "grupo_estudiante_id_ficha_inscripcion_key" '
                'UNIQUE ("id_ficha_inscripcion");'
            ),
        ),
        migrations.AlterField(
            model_name="grupoestudiante",
            name="ficha_inscripcion",
            field=models.ForeignKey(
                db_column="id_ficha_inscripcion",
                on_delete=django.db.models.deletion.CASCADE,
                related_name="asignaciones_grupo",
                to="matricula.fichainscripcion",
            ),
        ),
        migrations.AddField(
            model_name="grupoestudiante",
            name="periodo",
            field=models.ForeignKey(
                blank=True,
                db_column="id_periodo",
                null=True,
                on_delete=django.db.models.deletion.RESTRICT,
                related_name="asignaciones_estudiantes",
                to="academico.periodo",
            ),
        ),
        migrations.AddField(
            model_name="grupoestudiante",
            name="fecha_fin",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="grupoestudiante",
            name="estado",
            field=models.CharField(
                choices=[
                    ("activo", "Activo"),
                    ("finalizado", "Finalizado"),
                    ("retirado", "Retirado"),
                ],
                default="activo",
                max_length=20,
            ),
        ),
        migrations.RunPython(populate_assignment_periods, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="grupoestudiante",
            constraint=models.UniqueConstraint(
                condition=models.Q(periodo__isnull=False),
                fields=("ficha_inscripcion", "periodo"),
                name="uq_grupo_estudiante_ficha_periodo",
            ),
        ),
    ]
