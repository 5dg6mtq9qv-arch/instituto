from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("matricula", "0001_initial"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
                    ALTER TABLE matricula.curso
                        ADD COLUMN IF NOT EXISTS grado varchar(60),
                        ADD COLUMN IF NOT EXISTS carrera varchar(160),
                        ADD COLUMN IF NOT EXISTS universidad varchar(160),
                        ADD COLUMN IF NOT EXISTS id_empresa integer;

                    UPDATE matricula.curso
                    SET id_empresa = (
                        SELECT id
                        FROM core.empresa
                        WHERE activa = true
                        ORDER BY id
                        LIMIT 1
                    )
                    WHERE id_empresa IS NULL;

                    ALTER TABLE matricula.curso
                        ALTER COLUMN id_empresa SET NOT NULL;

                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1
                            FROM pg_constraint
                            WHERE conname = 'curso_id_empresa_f06c8ee6_fk_empresa_id'
                              AND conrelid = 'matricula.curso'::regclass
                        ) THEN
                            ALTER TABLE matricula.curso
                                ADD CONSTRAINT curso_id_empresa_f06c8ee6_fk_empresa_id
                                FOREIGN KEY (id_empresa)
                                REFERENCES core.empresa(id)
                                DEFERRABLE INITIALLY DEFERRED;
                        END IF;
                    END $$;

                    CREATE INDEX IF NOT EXISTS curso_id_empresa_f06c8ee6
                        ON matricula.curso (id_empresa);
                    """,
                    reverse_sql=migrations.RunSQL.noop,
                )
            ],
            state_operations=[],
        ),
    ]
