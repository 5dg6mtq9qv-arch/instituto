SQL_FICHA_INSCRIPCION = """
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
LEFT JOIN matricula.aula a ON a.id = fi.id_aula
"""
