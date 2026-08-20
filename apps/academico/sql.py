SQL_INDICADOR_PREGUNTAS_DOCENTE = """
SELECT
    bp.id_empresa,
    p.id_creado_por AS id_docente,
    docente.nombre AS docente,
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
GROUP BY bp.id_empresa, p.id_creado_por, docente.nombre, a.nombre, t.nombre, bp.tipo, bp.meta_preguntas
"""
