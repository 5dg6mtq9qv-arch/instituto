from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("auditoria", "0003_pagoauditoria_cuota_events"),
    ]

    operations = [
        migrations.AlterField(
            model_name="pagoauditoria",
            name="accion",
            field=models.CharField(
                choices=[
                    ("crear", "Creación"),
                    ("modificar", "Modificación"),
                    ("anular", "Anulación"),
                ],
                max_length=20,
            ),
        ),
    ]
