from django.db import migrations


VIEWS_SQL = """
CREATE OR REPLACE VIEW matricula.v_ficha_inscripcion AS
SELECT
    fi.id,
    fi.numero,
    fi.fecha,
    e.razon_social AS empresa,
    trim(concat_ws(' ', cliente.nombre, nullif(cliente.apellido, ''))) AS cliente,
    cliente.identificacion AS identificacion_cliente,
    trim(concat_ws(' ', estudiante.nombre, nullif(estudiante.apellido, ''))) AS estudiante,
    estudiante.identificacion AS identificacion_estudiante,
    trim(concat_ws(' ', representante.nombre, nullif(representante.apellido, ''))) AS representante,
    representante.identificacion AS identificacion_representante,
    pa.nombre AS periodo,
    c.nombre AS curso,
    a.nombre AS aula,
    fi.colegio,
    fi.carrera,
    fi.universidad,
    fi.valor_total_curso,
    fi.valor_matricula,
    fi.descuento,
    fi.abono,
    fi.saldo,
    fi.estado
FROM matricula.ficha_inscripcion fi
JOIN core.empresa e ON e.id = fi.id_empresa
JOIN core.partner cliente ON cliente.id = fi.id_cliente
JOIN core.partner estudiante ON estudiante.id = fi.id_estudiante
LEFT JOIN core.partner representante ON representante.id = fi.id_representante
LEFT JOIN matricula.periodo_academico pa ON pa.id = fi.id_periodo_academico
LEFT JOIN matricula.curso c ON c.id = fi.id_curso
LEFT JOIN matricula.aula a ON a.id = fi.id_aula;

CREATE OR REPLACE VIEW cartera.v_cartera_semaforo AS
SELECT
    cu.id,
    pp.id_empresa,
    fi.id AS id_ficha_inscripcion,
    fi.numero AS numero_ficha,
    trim(concat_ws(' ', estudiante.nombre, nullif(estudiante.apellido, ''))) AS estudiante,
    cu.numero,
    cu.fecha_pago_debito,
    cu.valor,
    cu.valor_pagado,
    (cu.valor - cu.valor_pagado) AS saldo,
    cu.estado,
    CASE
        WHEN cu.estado = 'pagada' THEN 'al_dia'
        WHEN cu.fecha_pago_debito < current_date - interval '30 days' THEN 'critico'
        WHEN cu.fecha_pago_debito < current_date THEN 'vencido'
        WHEN cu.fecha_pago_debito <= current_date + interval '7 days' THEN 'proximo'
        ELSE 'al_dia'
    END AS semaforo
FROM cartera.cuota cu
JOIN cartera.plan_pago pp ON pp.id = cu.id_plan_pago
JOIN matricula.ficha_inscripcion fi ON fi.id = pp.id_ficha_inscripcion
JOIN core.partner estudiante ON estudiante.id = fi.id_estudiante
WHERE cu.activo = true;

CREATE OR REPLACE VIEW academico.v_indicador_preguntas_docente AS
SELECT
    bp.id_empresa,
    p.id_creado_por AS id_docente,
    trim(concat_ws(' ', docente.nombre, nullif(docente.apellido, ''))) AS docente,
    a.nombre AS asignatura,
    t.nombre AS tema,
    bp.tipo,
    bp.meta_preguntas,
    count(p.id) AS preguntas_creadas,
    (bp.meta_preguntas - count(p.id)) AS preguntas_pendientes
FROM academico.banco_pregunta bp
JOIN academico.asignatura a ON a.id = bp.id_asignatura
LEFT JOIN academico.tema t ON t.id = bp.id_tema
LEFT JOIN academico.pregunta p ON p.id_banco_pregunta = bp.id AND p.activo = true
LEFT JOIN core.partner docente ON docente.id = p.id_creado_por
WHERE bp.activo = true
GROUP BY bp.id_empresa, p.id_creado_por, docente.nombre, docente.apellido, a.nombre, t.nombre, bp.tipo, bp.meta_preguntas;
"""


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0007_partner_apellido_split"),
    ]

    operations = [
        migrations.RunSQL(VIEWS_SQL, reverse_sql=migrations.RunSQL.noop),
    ]
