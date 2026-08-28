from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("matricula", "0002_reparar_schema_curso"),
    ]

    operations = [
        migrations.AlterField(
            model_name="fichainscripcion",
            name="periodo_academico",
            field=models.ForeignKey(
                blank=True,
                db_column="id_periodo_academico",
                null=True,
                on_delete=django.db.models.deletion.DO_NOTHING,
                to="matricula.periodoacademico",
            ),
        ),
    ]
