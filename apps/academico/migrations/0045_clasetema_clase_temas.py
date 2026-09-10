from django.db import migrations, models
import django.db.models.deletion


def copy_primary_topics(apps, schema_editor):
    Clase = apps.get_model("academico", "Clase")
    ClaseTema = apps.get_model("academico", "ClaseTema")
    rows = [
        ClaseTema(clase_id=clase_id, tema_id=tema_id, orden=1)
        for clase_id, tema_id in Clase.objects.exclude(tema_id__isnull=True).values_list("id", "tema_id")
    ]
    ClaseTema.objects.bulk_create(rows, ignore_conflicts=True)


class Migration(migrations.Migration):
    dependencies = [("academico", "0044_catalogos_planificacion_por_materia")]

    operations = [
        migrations.CreateModel(
            name="ClaseTema",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("orden", models.IntegerField(default=1)),
                (
                    "clase",
                    models.ForeignKey(
                        db_column="id_clase",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="clase_temas",
                        to="academico.clase",
                    ),
                ),
                (
                    "tema",
                    models.ForeignKey(
                        db_column="id_tema",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="clase_temas",
                        to="academico.tema",
                    ),
                ),
            ],
            options={
                "db_table": '"academico"."clase_tema"',
                "ordering": ["clase", "orden", "tema"],
                "unique_together": {("clase", "tema")},
            },
        ),
        migrations.AddField(
            model_name="clase",
            name="temas",
            field=models.ManyToManyField(
                blank=True,
                related_name="clases_asignadas",
                through="academico.ClaseTema",
                to="academico.tema",
            ),
        ),
        migrations.RunPython(copy_primary_topics, migrations.RunPython.noop),
    ]
