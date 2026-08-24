from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("academico", "0016_materia_color_sql"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AddField(
                    model_name="materia",
                    name="color",
                    field=models.CharField(default="#2563eb", max_length=7),
                ),
            ],
        ),
    ]
