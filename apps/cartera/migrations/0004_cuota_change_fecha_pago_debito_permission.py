from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("cartera", "0003_remove_direccion_financial_summary_permission"),
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
                ),
            },
        ),
    ]
