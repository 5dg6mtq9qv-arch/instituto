from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("academico", "0015_estado_clase"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE academico.materia
                    ADD COLUMN IF NOT EXISTS color VARCHAR(7) NOT NULL DEFAULT '#2563eb';
            """,
            reverse_sql="""
                ALTER TABLE academico.materia
                    DROP COLUMN IF EXISTS color;
            """,
        ),
    ]
