from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("academico", "0011_estado_materia_curso_horario"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            CREATE TABLE academico.periodo (
                id BIGSERIAL PRIMARY KEY,
                nombre VARCHAR(150) NOT NULL,
                fecha_inicio DATE NOT NULL,
                fecha_fin DATE NOT NULL,

                CONSTRAINT chk_periodo_fechas
                    CHECK (fecha_fin >= fecha_inicio)
            );

            CREATE TABLE academico.curso_periodo (
                id BIGSERIAL PRIMARY KEY,
                id_curso BIGINT NOT NULL,
                id_periodo BIGINT NOT NULL,

                CONSTRAINT fk_curso_periodo_curso
                    FOREIGN KEY (id_curso)
                    REFERENCES academico.curso(id)
                    ON DELETE CASCADE,

                CONSTRAINT fk_curso_periodo_periodo
                    FOREIGN KEY (id_periodo)
                    REFERENCES academico.periodo(id)
                    ON DELETE RESTRICT,

                CONSTRAINT uq_curso_periodo
                    UNIQUE (id_curso, id_periodo)
            );
            """,
            reverse_sql="""
            DROP TABLE IF EXISTS academico.curso_periodo;
            DROP TABLE IF EXISTS academico.periodo;
            """,
        ),
    ]
