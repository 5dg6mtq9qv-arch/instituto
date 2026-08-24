from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("academico", "0017_estado_materia_color"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                CREATE TABLE IF NOT EXISTS academico.profesor_materia_curso (
                    id BIGSERIAL PRIMARY KEY,
                    id_partner BIGINT NOT NULL,
                    id_materia_curso BIGINT NOT NULL,

                    CONSTRAINT fk_profesor_materia_curso_partner
                        FOREIGN KEY (id_partner)
                        REFERENCES core.partner(id)
                        ON DELETE RESTRICT,

                    CONSTRAINT fk_profesor_materia_curso_materia
                        FOREIGN KEY (id_materia_curso)
                        REFERENCES academico.materia_curso(id)
                        ON DELETE CASCADE,

                    CONSTRAINT uq_profesor_materia_curso
                        UNIQUE (id_partner, id_materia_curso)
                );
            """,
            reverse_sql="""
                DROP TABLE IF EXISTS academico.profesor_materia_curso;
            """,
        ),
    ]
