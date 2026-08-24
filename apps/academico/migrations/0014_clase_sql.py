from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("academico", "0013_estado_periodo_curso_periodo"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                CREATE TABLE IF NOT EXISTS academico.clase (
                    id BIGSERIAL PRIMARY KEY,
                    id_horario_aula_curso BIGINT NOT NULL,
                    id_materia_curso BIGINT NOT NULL,
                    fecha DATE NOT NULL,
                    descripcion TEXT,

                    CONSTRAINT fk_clase_horario
                        FOREIGN KEY (id_horario_aula_curso)
                        REFERENCES academico.horario_aula_curso(id)
                        ON DELETE CASCADE,

                    CONSTRAINT fk_clase_materia
                        FOREIGN KEY (id_materia_curso)
                        REFERENCES academico.materia_curso(id)
                        ON DELETE RESTRICT,

                    CONSTRAINT uq_clase_horario_fecha
                        UNIQUE (id_horario_aula_curso, fecha)
                );
            """,
            reverse_sql="""
                DROP TABLE IF EXISTS academico.clase;
            """,
        ),
    ]
