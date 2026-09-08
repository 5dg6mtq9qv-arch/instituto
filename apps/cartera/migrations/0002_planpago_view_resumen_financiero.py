from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("cartera", "0001_initial"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="planpago",
            options={
                "db_table": '"cartera"."plan_pago"',
                "ordering": ["-created"],
                "permissions": (
                    ("view_resumen_financiero", "Puede ver el resumen financiero de cartera"),
                ),
            },
        ),
    ]
