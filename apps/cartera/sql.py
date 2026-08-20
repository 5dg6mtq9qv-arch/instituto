SQL_CARTERA_SEMAFORO = """
SELECT
    cu.id,
    pp.id_empresa,
    fi.id AS id_ficha_inscripcion,
    fi.numero AS numero_ficha,
    estudiante.nombre AS estudiante,
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
WHERE cu.activo = true
"""
