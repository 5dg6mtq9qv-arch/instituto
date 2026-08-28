from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("matricula", "0003_fichainscripcion_periodo_optional"),
    ]

    operations = [
        migrations.AlterField(
            model_name="fichainscripcion",
            name="forma_pago_convenio",
            field=models.CharField(
                blank=True,
                choices=[
                    ("quincenal", "Quincenal"),
                    ("mensual", "Mensual"),
                    ("unico", "Pago unico"),
                ],
                max_length=20,
                null=True,
            ),
        ),
    ]
