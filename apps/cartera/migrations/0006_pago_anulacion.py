from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("cartera", "0005_cuota_change_valor_cuota_permission"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="pago",
            name="anulado",
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AddField(
            model_name="pago",
            name="fecha_anulacion",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="pago",
            name="motivo_anulacion",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="pago",
            name="usuario_anulacion",
            field=models.ForeignKey(
                blank=True,
                db_column="id_usuario_anulacion",
                null=True,
                on_delete=django.db.models.deletion.DO_NOTHING,
                related_name="pagos_anulados",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterModelOptions(
            name="pago",
            options={
                "ordering": ["-fecha_registro"],
                "permissions": (("anular_pago", "Puede anular pagos y revertir sus valores"),),
            },
        ),
    ]
