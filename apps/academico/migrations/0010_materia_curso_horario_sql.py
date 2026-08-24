from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("academico", "0009_estado_distribucion_grupos_cursos"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            CREATE TABLE academico.materia (
                id BIGSERIAL PRIMARY KEY,
                nombre VARCHAR(150) NOT NULL,
                nombre_corto VARCHAR(50),
                descripcion TEXT
            );

            CREATE TABLE academico.materia_curso (
                id BIGSERIAL PRIMARY KEY,
                id_materia BIGINT NOT NULL,
                id_grupo BIGINT NOT NULL,

                CONSTRAINT fk_materia_curso_materia
                    FOREIGN KEY (id_materia)
                    REFERENCES academico.materia(id)
                    ON DELETE RESTRICT,

                CONSTRAINT fk_materia_curso_grupo
                    FOREIGN KEY (id_grupo)
                    REFERENCES academico.curso(id)
                    ON DELETE CASCADE,

                CONSTRAINT uq_materia_curso
                    UNIQUE (id_materia, id_grupo)
            );

            CREATE TABLE academico.materia_horario (
                id BIGSERIAL PRIMARY KEY,
                id_materia_grupo BIGINT NOT NULL,
                id_horario_aula_curso BIGINT NOT NULL,

                CONSTRAINT fk_materia_horario_materia_grupo
                    FOREIGN KEY (id_materia_grupo)
                    REFERENCES academico.materia_curso(id)
                    ON DELETE CASCADE,

                CONSTRAINT fk_materia_horario_horario_aula_curso
                    FOREIGN KEY (id_horario_aula_curso)
                    REFERENCES academico.horario_aula_curso(id)
                    ON DELETE CASCADE,

                CONSTRAINT uq_materia_horario
                    UNIQUE (
                        id_materia_grupo,
                        id_horario_aula_curso
                    )
            );
            """,
            reverse_sql="""
            DROP TABLE IF EXISTS academico.materia_horario;
            DROP TABLE IF EXISTS academico.materia_curso;
            DROP TABLE IF EXISTS academico.materia;
            """,
        ),
    ]
