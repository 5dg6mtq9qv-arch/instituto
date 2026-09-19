from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("cartera", "0004_cuota_change_fecha_pago_debito_permission"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="cuota",
            options={
                "db_table": '"cartera"."cuota"',
                "ordering": ["fecha_pago_debito", "numero"],
                "permissions": (
                    (
                        "change_fecha_pago_debito",
                        "Puede editar manualmente la fecha de pago de una cuota",
                    ),
                    (
                        "change_valor_cuota",
                        "Puede editar el valor de una cuota sin pagos realizados",
                    ),
                ),
            },
        ),
    ]
