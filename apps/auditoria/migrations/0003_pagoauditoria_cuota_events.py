from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("auditoria", "0002_pagoauditoria"),
        ("cartera", "0005_cuota_change_valor_cuota_permission"),
    ]

    operations = [
        migrations.AddField(
            model_name="pagoauditoria",
            name="tipo_evento",
            field=models.CharField(
                choices=[("pago", "Pago"), ("cuota", "Cambio de cuota")],
                db_index=True,
                default="pago",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="pagoauditoria",
            name="pago_id",
            field=models.PositiveBigIntegerField(blank=True, db_index=True, null=True),
        ),
    ]
