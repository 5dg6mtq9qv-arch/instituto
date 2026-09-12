from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("academico", "0047_period_closure_assignment_history"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="periodo",
            options={
                "ordering": ["-fecha_inicio", "nombre"],
                "permissions": [("close_periodo", "Puede cerrar periodos academicos")],
            },
        ),
    ]
