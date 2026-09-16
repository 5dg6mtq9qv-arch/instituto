from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("academico", "0053_claseasistencia_edit_closed_permission"),
    ]

    operations = [
        migrations.AddField(
            model_name="clase",
            name="asistencia_cierre_automatico",
            field=models.BooleanField(default=False),
        ),
    ]
