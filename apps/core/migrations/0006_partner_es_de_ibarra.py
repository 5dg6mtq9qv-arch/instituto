from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0005_default_tipos_documento"),
    ]

    operations = [
        migrations.AddField(
            model_name="partner",
            name="es_de_ibarra",
            field=models.BooleanField(default=True),
        ),
    ]
