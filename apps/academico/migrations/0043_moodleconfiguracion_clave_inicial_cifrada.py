from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("academico", "0042_moodleconfiguracion"),
    ]

    operations = [
        migrations.AddField(
            model_name="moodleconfiguracion",
            name="clave_inicial_cifrada",
            field=models.TextField(blank=True, editable=False),
        ),
    ]
