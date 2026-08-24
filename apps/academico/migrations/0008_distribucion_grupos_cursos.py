from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("academico", "0007_alter_horarioclase_options"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            CREATE TABLE academico.curso (
                id BIGSERIAL PRIMARY KEY,
                nombre VARCHAR(150) NOT NULL,
                activo BOOLEAN NOT NULL DEFAULT TRUE,
                descripcion TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                id_usuario_updated BIGINT
            );

            CREATE TABLE academico.aula (
                id BIGSERIAL PRIMARY KEY,
                nombre VARCHAR(100) NOT NULL,
                descripcion TEXT
            );

            CREATE TABLE academico.aula_curso (
                id BIGSERIAL PRIMARY KEY,
                id_aula BIGINT NOT NULL,
                id_curso BIGINT NOT NULL,
                nombre VARCHAR(150),
                descripcion TEXT,

                CONSTRAINT fk_aula_curso_aula
                    FOREIGN KEY (id_aula)
                    REFERENCES academico.aula(id)
                    ON DELETE RESTRICT,

                CONSTRAINT fk_aula_curso_curso
                    FOREIGN KEY (id_curso)
                    REFERENCES academico.curso(id)
                    ON DELETE RESTRICT,

                CONSTRAINT uq_aula_curso
                    UNIQUE (id_aula, id_curso)
            );

            CREATE TABLE academico.dia (
                id BIGSERIAL PRIMARY KEY,
                dia VARCHAR(20) NOT NULL UNIQUE
            );

            CREATE TABLE academico.horario (
                id BIGSERIAL PRIMARY KEY,
                hora_inicio TIME NOT NULL,
                hora_fin TIME NOT NULL,

                CONSTRAINT chk_horario_horas
                    CHECK (hora_fin > hora_inicio)
            );

            CREATE TABLE academico.horario_dia (
                id BIGSERIAL PRIMARY KEY,
                id_dia BIGINT NOT NULL,
                id_horario BIGINT NOT NULL,

                CONSTRAINT fk_horario_dia_dia
                    FOREIGN KEY (id_dia)
                    REFERENCES academico.dia(id)
                    ON DELETE CASCADE,

                CONSTRAINT fk_horario_dia_horario
                    FOREIGN KEY (id_horario)
                    REFERENCES academico.horario(id)
                    ON DELETE CASCADE,

                CONSTRAINT uq_horario_dia
                    UNIQUE (id_dia, id_horario)
            );

            CREATE TABLE academico.horario_aula_curso (
                id BIGSERIAL PRIMARY KEY,
                id_aula_curso BIGINT NOT NULL,
                id_horario_dia BIGINT NOT NULL,

                CONSTRAINT fk_horario_aula_curso
                    FOREIGN KEY (id_aula_curso)
                    REFERENCES academico.aula_curso(id)
                    ON DELETE CASCADE,

                CONSTRAINT fk_horario_aula_curso_horario
                    FOREIGN KEY (id_horario_dia)
                    REFERENCES academico.horario_dia(id)
                    ON DELETE CASCADE,

                CONSTRAINT uq_horario_aula_curso
                    UNIQUE (id_aula_curso, id_horario_dia)
            );

            INSERT INTO academico.dia (dia)
            VALUES
                ('Lunes'),
                ('Martes'),
                ('Miercoles'),
                ('Jueves'),
                ('Viernes'),
                ('Sabado'),
                ('Domingo');
            """,
            reverse_sql="""
            DROP TABLE IF EXISTS academico.horario_aula_curso;
            DROP TABLE IF EXISTS academico.horario_dia;
            DROP TABLE IF EXISTS academico.horario;
            DROP TABLE IF EXISTS academico.dia;
            DROP TABLE IF EXISTS academico.aula_curso;
            DROP TABLE IF EXISTS academico.aula;
            DROP TABLE IF EXISTS academico.curso;
            """,
        ),
    ]
