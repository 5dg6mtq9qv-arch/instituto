-- Propuesta de esquema para revision.
-- No fue aplicado a la base instituto.
-- Convencion tomada de mantis-core/difarmedic:
--   * esquemas por modulo
--   * tablas singulares en espanol
--   * columnas FK como id_*
--   * timestamps created/updated y usuario_updated
--   * activo para desactivar sin borrar historial
--   * vistas SQL para indicadores

CREATE EXTENSION IF NOT EXISTS hstore;

CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS matricula;
CREATE SCHEMA IF NOT EXISTS academico;
CREATE SCHEMA IF NOT EXISTS cartera;
CREATE SCHEMA IF NOT EXISTS auditoria;

-- ============================================================
-- CORE
-- ============================================================

CREATE TABLE IF NOT EXISTS core.tipo_identificacion (
    id serial PRIMARY KEY,
    nombre varchar(30) NOT NULL,
    codigo varchar(10),
    activo boolean NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS core.empresa (
    id serial PRIMARY KEY,
    ruc varchar(13) NOT NULL DEFAULT '',
    razon_social varchar(300),
    nombre_comercial varchar(300),
    direccion text NOT NULL DEFAULT '',
    telefono varchar(20),
    email text,
    ciudad varchar(80),
    logo text,
    activa boolean NOT NULL DEFAULT true,
    tags hstore DEFAULT ''::hstore,
    created timestamp without time zone NOT NULL DEFAULT now(),
    updated timestamp without time zone NOT NULL DEFAULT now(),
    id_usuario_updated integer
);

CREATE TABLE IF NOT EXISTS core.operador_movil (
    id serial PRIMARY KEY,
    nombre varchar(100) NOT NULL,
    comentario varchar(200),
    activo boolean NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS core.partner (
    id serial PRIMARY KEY,
    codigo varchar(50),
    codigo_aux varchar(20),
    nombre text NOT NULL,
    id_tipo_identificacion integer NOT NULL,
    identificacion varchar(20) NOT NULL DEFAULT '',
    direccion varchar(200),
    telefono varchar(50),
    telefono_celular varchar(50),
    email text,
    fecha_nacimiento date,
    genero varchar(1),
    tipo varchar(2),
    ocupacion varchar(100),
    comentario text,
    id_empresa integer,
    id_operador_movil integer,
    es_cliente boolean NOT NULL DEFAULT true,
    es_estudiante boolean NOT NULL DEFAULT false,
    es_representante boolean NOT NULL DEFAULT false,
    es_docente boolean NOT NULL DEFAULT false,
    ingresar_portal boolean DEFAULT true,
    activo boolean DEFAULT true,
    tags hstore DEFAULT ''::hstore,
    creado timestamp without time zone NOT NULL DEFAULT now(),
    actualizado timestamp without time zone NOT NULL DEFAULT now(),
    id_usuario_updated integer,
    CONSTRAINT partner_identificacion_key UNIQUE (identificacion),
    CONSTRAINT partner_tipo_identificacion_fk
        FOREIGN KEY (id_tipo_identificacion)
        REFERENCES core.tipo_identificacion(id)
        ON UPDATE CASCADE,
    CONSTRAINT partner_empresa_fk
        FOREIGN KEY (id_empresa)
        REFERENCES core.empresa(id)
        ON UPDATE CASCADE,
    CONSTRAINT partner_operador_movil_fk
        FOREIGN KEY (id_operador_movil)
        REFERENCES core.operador_movil(id)
        ON UPDATE CASCADE
);

CREATE INDEX IF NOT EXISTS partner_id_empresa_idx ON core.partner (id_empresa);
CREATE INDEX IF NOT EXISTS partner_identificacion_idx ON core.partner (identificacion);
CREATE INDEX IF NOT EXISTS partner_nombre_idx ON core.partner USING gin (to_tsvector('spanish', nombre));

CREATE TABLE IF NOT EXISTS core.partner_partner (
    id serial PRIMARY KEY,
    id_partner_a integer NOT NULL,
    id_partner_b integer NOT NULL,
    relacion varchar(50) NOT NULL,
    principal boolean NOT NULL DEFAULT false,
    contacto_emergencia boolean NOT NULL DEFAULT true,
    activo boolean NOT NULL DEFAULT true,
    created timestamp without time zone NOT NULL DEFAULT now(),
    updated timestamp without time zone NOT NULL DEFAULT now(),
    id_usuario_updated integer,
    CONSTRAINT partner_partner_unique UNIQUE (id_partner_a, id_partner_b, relacion),
    CONSTRAINT partner_partner_a_fk
        FOREIGN KEY (id_partner_a) REFERENCES core.partner(id) ON UPDATE CASCADE,
    CONSTRAINT partner_partner_b_fk
        FOREIGN KEY (id_partner_b) REFERENCES core.partner(id) ON UPDATE CASCADE
);

-- ============================================================
-- MATRICULA / FICHA DE INSCRIPCION
-- ============================================================

CREATE TABLE IF NOT EXISTS matricula.periodo_academico (
    id serial PRIMARY KEY,
    id_empresa integer NOT NULL,
    nombre varchar(120) NOT NULL,
    regimen varchar(60),
    fecha_inicio date,
    fecha_fin date,
    estado varchar(20) NOT NULL DEFAULT 'borrador',
    activo boolean NOT NULL DEFAULT true,
    created timestamp without time zone NOT NULL DEFAULT now(),
    updated timestamp without time zone NOT NULL DEFAULT now(),
    id_usuario_updated integer,
    CONSTRAINT periodo_academico_empresa_fk
        FOREIGN KEY (id_empresa) REFERENCES core.empresa(id) ON UPDATE CASCADE,
    CONSTRAINT periodo_academico_empresa_nombre_key UNIQUE (id_empresa, nombre)
);

CREATE TABLE IF NOT EXISTS matricula.curso (
    id serial PRIMARY KEY,
    id_empresa integer NOT NULL,
    nombre varchar(120) NOT NULL,
    grado varchar(60),
    carrera varchar(160),
    universidad varchar(160),
    activo boolean NOT NULL DEFAULT true,
    created timestamp without time zone NOT NULL DEFAULT now(),
    updated timestamp without time zone NOT NULL DEFAULT now(),
    id_usuario_updated integer,
    CONSTRAINT curso_empresa_fk
        FOREIGN KEY (id_empresa) REFERENCES core.empresa(id) ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS matricula.aula (
    id serial PRIMARY KEY,
    id_empresa integer NOT NULL,
    id_periodo_academico integer NOT NULL,
    nombre varchar(120) NOT NULL,
    seccion varchar(40),
    jornada varchar(40),
    horario varchar(120),
    hora varchar(80),
    duracion varchar(80),
    capacidad integer DEFAULT 0,
    activo boolean NOT NULL DEFAULT true,
    created timestamp without time zone NOT NULL DEFAULT now(),
    updated timestamp without time zone NOT NULL DEFAULT now(),
    id_usuario_updated integer,
    CONSTRAINT aula_empresa_fk
        FOREIGN KEY (id_empresa) REFERENCES core.empresa(id) ON UPDATE CASCADE,
    CONSTRAINT aula_periodo_fk
        FOREIGN KEY (id_periodo_academico) REFERENCES matricula.periodo_academico(id) ON UPDATE CASCADE,
    CONSTRAINT aula_periodo_nombre_key UNIQUE (id_periodo_academico, nombre, seccion)
);

CREATE TABLE IF NOT EXISTS matricula.ficha_inscripcion (
    id serial PRIMARY KEY,
    id_empresa integer NOT NULL,
    numero varchar(30) NOT NULL,
    fecha date NOT NULL DEFAULT current_date,
    id_periodo_academico integer NOT NULL,
    id_curso integer,
    id_aula integer,
    id_cliente integer NOT NULL,
    id_estudiante integer NOT NULL,
    id_representante integer,
    edad integer,
    colegio varchar(200),
    curso_grado varchar(120),
    nota_grado varchar(60),
    carrera varchar(160),
    universidad varchar(160),
    nombre_conyuge varchar(200),
    ocupacion_conyuge varchar(120),
    correo_estudiante text,
    correo_representante text,
    horario varchar(120),
    hora varchar(80),
    duracion varchar(80),
    forma_pago_convenio varchar(20), -- quincenal, mensual, unico
    fecha_proximo_pago date,
    valor_proximo_pago numeric(12,2) DEFAULT 0,
    valor_total_curso numeric(12,2) NOT NULL DEFAULT 0,
    valor_matricula numeric(12,2) NOT NULL DEFAULT 0,
    descuento numeric(12,2) NOT NULL DEFAULT 0,
    abono numeric(12,2) NOT NULL DEFAULT 0,
    saldo numeric(12,2) NOT NULL DEFAULT 0,
    promo boolean NOT NULL DEFAULT false,
    autorizacion_imagen boolean NOT NULL DEFAULT false,
    acepta_garantia boolean NOT NULL DEFAULT false,
    acepta_no_devolucion boolean NOT NULL DEFAULT false,
    firma_representante text,
    ci_representante_firma varchar(20),
    firma_director_asesor text,
    ci_director_asesor varchar(20),
    archivo_contrato text,
    archivo_ficha_firmada text,
    estado varchar(20) NOT NULL DEFAULT 'borrador',
    observacion text,
    activo boolean NOT NULL DEFAULT true,
    created timestamp without time zone NOT NULL DEFAULT now(),
    updated timestamp without time zone NOT NULL DEFAULT now(),
    id_usuario_updated integer,
    CONSTRAINT ficha_inscripcion_empresa_fk
        FOREIGN KEY (id_empresa) REFERENCES core.empresa(id) ON UPDATE CASCADE,
    CONSTRAINT ficha_inscripcion_periodo_fk
        FOREIGN KEY (id_periodo_academico) REFERENCES matricula.periodo_academico(id) ON UPDATE CASCADE,
    CONSTRAINT ficha_inscripcion_curso_fk
        FOREIGN KEY (id_curso) REFERENCES matricula.curso(id) ON UPDATE CASCADE,
    CONSTRAINT ficha_inscripcion_aula_fk
        FOREIGN KEY (id_aula) REFERENCES matricula.aula(id) ON UPDATE CASCADE,
    CONSTRAINT ficha_inscripcion_cliente_fk
        FOREIGN KEY (id_cliente) REFERENCES core.partner(id) ON UPDATE CASCADE,
    CONSTRAINT ficha_inscripcion_estudiante_fk
        FOREIGN KEY (id_estudiante) REFERENCES core.partner(id) ON UPDATE CASCADE,
    CONSTRAINT ficha_inscripcion_representante_fk
        FOREIGN KEY (id_representante) REFERENCES core.partner(id) ON UPDATE CASCADE,
    CONSTRAINT ficha_inscripcion_numero_key UNIQUE (id_empresa, numero)
);

CREATE INDEX IF NOT EXISTS ficha_inscripcion_estudiante_idx
    ON matricula.ficha_inscripcion (id_estudiante);
CREATE INDEX IF NOT EXISTS ficha_inscripcion_cliente_idx
    ON matricula.ficha_inscripcion (id_cliente);
CREATE INDEX IF NOT EXISTS ficha_inscripcion_estado_idx
    ON matricula.ficha_inscripcion (estado);

CREATE TABLE IF NOT EXISTS matricula.aula_historial (
    id serial PRIMARY KEY,
    id_ficha_inscripcion integer NOT NULL,
    id_aula_origen integer,
    id_aula_destino integer NOT NULL,
    fecha_cambio timestamp without time zone NOT NULL DEFAULT now(),
    motivo text,
    id_usuario integer,
    CONSTRAINT aula_historial_ficha_fk
        FOREIGN KEY (id_ficha_inscripcion) REFERENCES matricula.ficha_inscripcion(id) ON UPDATE CASCADE,
    CONSTRAINT aula_historial_origen_fk
        FOREIGN KEY (id_aula_origen) REFERENCES matricula.aula(id) ON UPDATE CASCADE,
    CONSTRAINT aula_historial_destino_fk
        FOREIGN KEY (id_aula_destino) REFERENCES matricula.aula(id) ON UPDATE CASCADE
);

-- ============================================================
-- CARTERA / CONVENIO DE PAGO
-- ============================================================

CREATE TABLE IF NOT EXISTS cartera.forma_pago (
    id serial PRIMARY KEY,
    id_empresa integer NOT NULL,
    nombre varchar(30) NOT NULL,
    tipo varchar(20),
    activo boolean NOT NULL DEFAULT true,
    orden integer,
    es_venta boolean DEFAULT true,
    es_pago boolean DEFAULT true,
    created timestamp without time zone NOT NULL DEFAULT now(),
    updated timestamp without time zone NOT NULL DEFAULT now(),
    id_usuario_updated integer,
    CONSTRAINT forma_pago_empresa_fk
        FOREIGN KEY (id_empresa) REFERENCES core.empresa(id) ON UPDATE CASCADE,
    CONSTRAINT forma_pago_empresa_tipo_key UNIQUE (id_empresa, tipo)
);

CREATE TABLE IF NOT EXISTS cartera.plan_pago (
    id serial PRIMARY KEY,
    id_empresa integer NOT NULL,
    id_ficha_inscripcion integer NOT NULL,
    valor_total numeric(12,2) NOT NULL DEFAULT 0,
    valor_matricula numeric(12,2) NOT NULL DEFAULT 0,
    descuento numeric(12,2) NOT NULL DEFAULT 0,
    abono numeric(12,2) NOT NULL DEFAULT 0,
    saldo numeric(12,2) NOT NULL DEFAULT 0,
    estado varchar(20) NOT NULL DEFAULT 'activo',
    observacion text,
    activo boolean NOT NULL DEFAULT true,
    created timestamp without time zone NOT NULL DEFAULT now(),
    updated timestamp without time zone NOT NULL DEFAULT now(),
    id_usuario_updated integer,
    CONSTRAINT plan_pago_empresa_fk
        FOREIGN KEY (id_empresa) REFERENCES core.empresa(id) ON UPDATE CASCADE,
    CONSTRAINT plan_pago_ficha_fk
        FOREIGN KEY (id_ficha_inscripcion) REFERENCES matricula.ficha_inscripcion(id) ON UPDATE CASCADE,
    CONSTRAINT plan_pago_ficha_key UNIQUE (id_ficha_inscripcion)
);

CREATE TABLE IF NOT EXISTS cartera.cuota (
    id serial PRIMARY KEY,
    id_plan_pago integer NOT NULL,
    numero integer NOT NULL,
    fecha_pago_debito date NOT NULL,
    valor numeric(12,2) NOT NULL DEFAULT 0,
    valor_pagado numeric(12,2) NOT NULL DEFAULT 0,
    numero_recibo_factura_deposito varchar(60),
    observacion text,
    estado varchar(20) NOT NULL DEFAULT 'pendiente',
    prioridad varchar(20) NOT NULL DEFAULT 'normal',
    activo boolean NOT NULL DEFAULT true,
    created timestamp without time zone NOT NULL DEFAULT now(),
    updated timestamp without time zone NOT NULL DEFAULT now(),
    id_usuario_updated integer,
    CONSTRAINT cuota_plan_pago_fk
        FOREIGN KEY (id_plan_pago) REFERENCES cartera.plan_pago(id) ON UPDATE CASCADE,
    CONSTRAINT cuota_plan_numero_key UNIQUE (id_plan_pago, numero)
);

CREATE INDEX IF NOT EXISTS cuota_fecha_pago_idx ON cartera.cuota (fecha_pago_debito);
CREATE INDEX IF NOT EXISTS cuota_estado_idx ON cartera.cuota (estado);

CREATE TABLE IF NOT EXISTS cartera.pago (
    id serial PRIMARY KEY,
    id_empresa integer NOT NULL,
    id_cuota integer NOT NULL,
    id_forma_pago integer NOT NULL,
    fecha_registro timestamp without time zone NOT NULL DEFAULT now(),
    valor numeric(12,2) NOT NULL DEFAULT 0,
    numero_documento varchar(60),
    comprobante text,
    comentario text,
    id_usuario integer,
    created timestamp without time zone NOT NULL DEFAULT now(),
    updated timestamp without time zone NOT NULL DEFAULT now(),
    id_usuario_updated integer,
    CONSTRAINT pago_empresa_fk
        FOREIGN KEY (id_empresa) REFERENCES core.empresa(id) ON UPDATE CASCADE,
    CONSTRAINT pago_cuota_fk
        FOREIGN KEY (id_cuota) REFERENCES cartera.cuota(id) ON UPDATE CASCADE,
    CONSTRAINT pago_forma_pago_fk
        FOREIGN KEY (id_forma_pago) REFERENCES cartera.forma_pago(id) ON UPDATE CASCADE
);

-- ============================================================
-- ACADEMICO
-- ============================================================

CREATE TABLE IF NOT EXISTS academico.asignatura (
    id serial PRIMARY KEY,
    id_empresa integer NOT NULL,
    codigo varchar(40) NOT NULL,
    nombre varchar(160) NOT NULL,
    activo boolean NOT NULL DEFAULT true,
    created timestamp without time zone NOT NULL DEFAULT now(),
    updated timestamp without time zone NOT NULL DEFAULT now(),
    id_usuario_updated integer,
    CONSTRAINT asignatura_empresa_fk
        FOREIGN KEY (id_empresa) REFERENCES core.empresa(id) ON UPDATE CASCADE,
    CONSTRAINT asignatura_empresa_codigo_key UNIQUE (id_empresa, codigo)
);

CREATE TABLE IF NOT EXISTS academico.temario (
    id serial PRIMARY KEY,
    id_empresa integer NOT NULL,
    id_periodo_academico integer,
    id_asignatura integer NOT NULL,
    nombre varchar(180) NOT NULL,
    estado varchar(20) NOT NULL DEFAULT 'borrador',
    activo boolean NOT NULL DEFAULT true,
    created timestamp without time zone NOT NULL DEFAULT now(),
    updated timestamp without time zone NOT NULL DEFAULT now(),
    id_usuario_updated integer,
    CONSTRAINT temario_empresa_fk
        FOREIGN KEY (id_empresa) REFERENCES core.empresa(id) ON UPDATE CASCADE,
    CONSTRAINT temario_periodo_fk
        FOREIGN KEY (id_periodo_academico) REFERENCES matricula.periodo_academico(id) ON UPDATE CASCADE,
    CONSTRAINT temario_asignatura_fk
        FOREIGN KEY (id_asignatura) REFERENCES academico.asignatura(id) ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS academico.tema (
    id serial PRIMARY KEY,
    id_temario integer NOT NULL,
    nombre varchar(180) NOT NULL,
    orden integer NOT NULL DEFAULT 1,
    objetivo text,
    numero_clases integer NOT NULL DEFAULT 1,
    dificultad varchar(20) DEFAULT 'media',
    meta_preguntas_proceso integer NOT NULL DEFAULT 10,
    meta_preguntas_final integer NOT NULL DEFAULT 10,
    activo boolean NOT NULL DEFAULT true,
    created timestamp without time zone NOT NULL DEFAULT now(),
    updated timestamp without time zone NOT NULL DEFAULT now(),
    id_usuario_updated integer,
    CONSTRAINT tema_temario_fk
        FOREIGN KEY (id_temario) REFERENCES academico.temario(id) ON UPDATE CASCADE,
    CONSTRAINT tema_temario_orden_key UNIQUE (id_temario, orden)
);

CREATE TABLE IF NOT EXISTS academico.subtema (
    id serial PRIMARY KEY,
    id_tema integer NOT NULL,
    nombre varchar(180) NOT NULL,
    orden integer NOT NULL DEFAULT 1,
    objetivo text,
    activo boolean NOT NULL DEFAULT true,
    created timestamp without time zone NOT NULL DEFAULT now(),
    updated timestamp without time zone NOT NULL DEFAULT now(),
    id_usuario_updated integer,
    CONSTRAINT subtema_tema_fk
        FOREIGN KEY (id_tema) REFERENCES academico.tema(id) ON UPDATE CASCADE,
    CONSTRAINT subtema_tema_orden_key UNIQUE (id_tema, orden)
);

CREATE TABLE IF NOT EXISTS academico.docente_asignatura (
    id serial PRIMARY KEY,
    id_empresa integer NOT NULL,
    id_docente integer NOT NULL,
    id_asignatura integer NOT NULL,
    id_periodo_academico integer NOT NULL,
    id_aula integer,
    activo boolean NOT NULL DEFAULT true,
    created timestamp without time zone NOT NULL DEFAULT now(),
    updated timestamp without time zone NOT NULL DEFAULT now(),
    id_usuario_updated integer,
    CONSTRAINT docente_asignatura_empresa_fk
        FOREIGN KEY (id_empresa) REFERENCES core.empresa(id) ON UPDATE CASCADE,
    CONSTRAINT docente_asignatura_docente_fk
        FOREIGN KEY (id_docente) REFERENCES core.partner(id) ON UPDATE CASCADE,
    CONSTRAINT docente_asignatura_asignatura_fk
        FOREIGN KEY (id_asignatura) REFERENCES academico.asignatura(id) ON UPDATE CASCADE,
    CONSTRAINT docente_asignatura_periodo_fk
        FOREIGN KEY (id_periodo_academico) REFERENCES matricula.periodo_academico(id) ON UPDATE CASCADE,
    CONSTRAINT docente_asignatura_aula_fk
        FOREIGN KEY (id_aula) REFERENCES matricula.aula(id) ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS academico.planificacion_clase (
    id serial PRIMARY KEY,
    id_empresa integer NOT NULL,
    id_docente integer NOT NULL,
    id_aula integer NOT NULL,
    id_asignatura integer NOT NULL,
    id_tema integer NOT NULL,
    id_subtema integer,
    numero_clase integer NOT NULL DEFAULT 1,
    fecha_planificada date NOT NULL,
    objetivo text NOT NULL,
    actividades text NOT NULL,
    recursos_previstos text,
    estado varchar(20) NOT NULL DEFAULT 'borrador',
    id_revisado_por integer,
    fecha_revision timestamp without time zone,
    notas_revision text,
    activo boolean NOT NULL DEFAULT true,
    created timestamp without time zone NOT NULL DEFAULT now(),
    updated timestamp without time zone NOT NULL DEFAULT now(),
    id_usuario_updated integer,
    CONSTRAINT planificacion_empresa_fk
        FOREIGN KEY (id_empresa) REFERENCES core.empresa(id) ON UPDATE CASCADE,
    CONSTRAINT planificacion_docente_fk
        FOREIGN KEY (id_docente) REFERENCES core.partner(id) ON UPDATE CASCADE,
    CONSTRAINT planificacion_aula_fk
        FOREIGN KEY (id_aula) REFERENCES matricula.aula(id) ON UPDATE CASCADE,
    CONSTRAINT planificacion_asignatura_fk
        FOREIGN KEY (id_asignatura) REFERENCES academico.asignatura(id) ON UPDATE CASCADE,
    CONSTRAINT planificacion_tema_fk
        FOREIGN KEY (id_tema) REFERENCES academico.tema(id) ON UPDATE CASCADE,
    CONSTRAINT planificacion_subtema_fk
        FOREIGN KEY (id_subtema) REFERENCES academico.subtema(id) ON UPDATE CASCADE,
    CONSTRAINT planificacion_revisado_por_fk
        FOREIGN KEY (id_revisado_por) REFERENCES core.partner(id) ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS academico.recurso_clase (
    id serial PRIMARY KEY,
    id_planificacion_clase integer NOT NULL,
    titulo varchar(180) NOT NULL,
    tipo varchar(20) NOT NULL DEFAULT 'documento',
    url text,
    archivo text,
    listo boolean NOT NULL DEFAULT false,
    id_creado_por integer,
    created timestamp without time zone NOT NULL DEFAULT now(),
    updated timestamp without time zone NOT NULL DEFAULT now(),
    id_usuario_updated integer,
    CONSTRAINT recurso_planificacion_fk
        FOREIGN KEY (id_planificacion_clase) REFERENCES academico.planificacion_clase(id) ON UPDATE CASCADE,
    CONSTRAINT recurso_creado_por_fk
        FOREIGN KEY (id_creado_por) REFERENCES core.partner(id) ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS academico.banco_pregunta (
    id serial PRIMARY KEY,
    id_empresa integer NOT NULL,
    id_asignatura integer NOT NULL,
    id_tema integer,
    id_subtema integer,
    tipo varchar(20) NOT NULL, -- proceso, final
    meta_preguntas integer NOT NULL DEFAULT 10,
    revisado_coordinacion boolean NOT NULL DEFAULT false,
    activo boolean NOT NULL DEFAULT true,
    created timestamp without time zone NOT NULL DEFAULT now(),
    updated timestamp without time zone NOT NULL DEFAULT now(),
    id_usuario_updated integer,
    CONSTRAINT banco_pregunta_empresa_fk
        FOREIGN KEY (id_empresa) REFERENCES core.empresa(id) ON UPDATE CASCADE,
    CONSTRAINT banco_pregunta_asignatura_fk
        FOREIGN KEY (id_asignatura) REFERENCES academico.asignatura(id) ON UPDATE CASCADE,
    CONSTRAINT banco_pregunta_tema_fk
        FOREIGN KEY (id_tema) REFERENCES academico.tema(id) ON UPDATE CASCADE,
    CONSTRAINT banco_pregunta_subtema_fk
        FOREIGN KEY (id_subtema) REFERENCES academico.subtema(id) ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS academico.pregunta (
    id serial PRIMARY KEY,
    id_banco_pregunta integer NOT NULL,
    id_creado_por integer NOT NULL,
    enunciado text NOT NULL,
    respuestas jsonb NOT NULL DEFAULT '[]'::jsonb,
    respuesta_correcta text,
    explicacion text,
    dificultad varchar(20) NOT NULL DEFAULT 'media',
    estado varchar(20) NOT NULL DEFAULT 'borrador',
    id_revisado_por integer,
    fecha_revision timestamp without time zone,
    notas_revision text,
    activo boolean NOT NULL DEFAULT true,
    created timestamp without time zone NOT NULL DEFAULT now(),
    updated timestamp without time zone NOT NULL DEFAULT now(),
    id_usuario_updated integer,
    CONSTRAINT pregunta_banco_fk
        FOREIGN KEY (id_banco_pregunta) REFERENCES academico.banco_pregunta(id) ON UPDATE CASCADE,
    CONSTRAINT pregunta_creado_por_fk
        FOREIGN KEY (id_creado_por) REFERENCES core.partner(id) ON UPDATE CASCADE,
    CONSTRAINT pregunta_revisado_por_fk
        FOREIGN KEY (id_revisado_por) REFERENCES core.partner(id) ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS academico.asistencia (
    id serial PRIMARY KEY,
    id_planificacion_clase integer NOT NULL,
    id_estudiante integer NOT NULL,
    estado varchar(20) NOT NULL,
    observacion text,
    id_registrado_por integer,
    created timestamp without time zone NOT NULL DEFAULT now(),
    updated timestamp without time zone NOT NULL DEFAULT now(),
    id_usuario_updated integer,
    CONSTRAINT asistencia_planificacion_fk
        FOREIGN KEY (id_planificacion_clase) REFERENCES academico.planificacion_clase(id) ON UPDATE CASCADE,
    CONSTRAINT asistencia_estudiante_fk
        FOREIGN KEY (id_estudiante) REFERENCES core.partner(id) ON UPDATE CASCADE,
    CONSTRAINT asistencia_registrado_por_fk
        FOREIGN KEY (id_registrado_por) REFERENCES core.partner(id) ON UPDATE CASCADE,
    CONSTRAINT asistencia_plan_estudiante_key UNIQUE (id_planificacion_clase, id_estudiante)
);

CREATE TABLE IF NOT EXISTS academico.evaluacion (
    id serial PRIMARY KEY,
    id_empresa integer NOT NULL,
    id_planificacion_clase integer,
    id_asignatura integer NOT NULL,
    id_tema integer,
    titulo varchar(180) NOT NULL,
    tipo varchar(20) NOT NULL DEFAULT 'proceso',
    fecha date NOT NULL,
    puntaje_maximo numeric(5,2) NOT NULL DEFAULT 10,
    id_creado_por integer,
    created timestamp without time zone NOT NULL DEFAULT now(),
    updated timestamp without time zone NOT NULL DEFAULT now(),
    id_usuario_updated integer,
    CONSTRAINT evaluacion_empresa_fk
        FOREIGN KEY (id_empresa) REFERENCES core.empresa(id) ON UPDATE CASCADE,
    CONSTRAINT evaluacion_planificacion_fk
        FOREIGN KEY (id_planificacion_clase) REFERENCES academico.planificacion_clase(id) ON UPDATE CASCADE,
    CONSTRAINT evaluacion_asignatura_fk
        FOREIGN KEY (id_asignatura) REFERENCES academico.asignatura(id) ON UPDATE CASCADE,
    CONSTRAINT evaluacion_tema_fk
        FOREIGN KEY (id_tema) REFERENCES academico.tema(id) ON UPDATE CASCADE,
    CONSTRAINT evaluacion_creado_por_fk
        FOREIGN KEY (id_creado_por) REFERENCES core.partner(id) ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS academico.evaluacion_resultado (
    id serial PRIMARY KEY,
    id_evaluacion integer NOT NULL,
    id_estudiante integer NOT NULL,
    nota numeric(5,2) NOT NULL DEFAULT 0,
    observacion text,
    created timestamp without time zone NOT NULL DEFAULT now(),
    updated timestamp without time zone NOT NULL DEFAULT now(),
    id_usuario_updated integer,
    CONSTRAINT evaluacion_resultado_evaluacion_fk
        FOREIGN KEY (id_evaluacion) REFERENCES academico.evaluacion(id) ON UPDATE CASCADE,
    CONSTRAINT evaluacion_resultado_estudiante_fk
        FOREIGN KEY (id_estudiante) REFERENCES core.partner(id) ON UPDATE CASCADE,
    CONSTRAINT evaluacion_resultado_key UNIQUE (id_evaluacion, id_estudiante)
);

-- ============================================================
-- AUDITORIA
-- ============================================================

CREATE TABLE IF NOT EXISTS auditoria.log_accion (
    id serial PRIMARY KEY,
    id_empresa integer,
    id_usuario integer,
    accion varchar(20) NOT NULL,
    modelo varchar(120) NOT NULL,
    object_id varchar(80),
    object_repr varchar(255),
    cambios jsonb NOT NULL DEFAULT '{}'::jsonb,
    ip_address inet,
    user_agent text,
    created timestamp without time zone NOT NULL DEFAULT now(),
    CONSTRAINT log_accion_empresa_fk
        FOREIGN KEY (id_empresa) REFERENCES core.empresa(id) ON UPDATE CASCADE
);

-- ============================================================
-- VISTAS
-- ============================================================

CREATE OR REPLACE VIEW matricula.v_ficha_inscripcion AS
SELECT
    fi.id,
    fi.numero,
    fi.fecha,
    e.razon_social AS empresa,
    cliente.nombre AS cliente,
    cliente.identificacion AS identificacion_cliente,
    estudiante.nombre AS estudiante,
    estudiante.identificacion AS identificacion_estudiante,
    representante.nombre AS representante,
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
JOIN matricula.periodo_academico pa ON pa.id = fi.id_periodo_academico
LEFT JOIN matricula.curso c ON c.id = fi.id_curso
LEFT JOIN matricula.aula a ON a.id = fi.id_aula;

CREATE OR REPLACE VIEW cartera.v_cartera_semaforo AS
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
WHERE cu.activo = true;

CREATE OR REPLACE VIEW academico.v_indicador_preguntas_docente AS
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
GROUP BY bp.id_empresa, p.id_creado_por, docente.nombre, a.nombre, t.nombre, bp.tipo, bp.meta_preguntas;

-- ============================================================
-- DATOS BASE SUGERIDOS
-- ============================================================

INSERT INTO core.tipo_identificacion (nombre, codigo, activo)
VALUES
    ('Cedula', '05', true),
    ('RUC', '04', true),
    ('Pasaporte', '06', true)
ON CONFLICT DO NOTHING;

-- Las formas de pago se crean despues de tener core.empresa.id.
-- INSERT INTO cartera.forma_pago (id_empresa, nombre, tipo, orden)
-- VALUES
--     (1, 'Efectivo', 'efectivo', 1),
--     (1, 'Transferencia', 'transferencia', 2),
--     (1, 'Cheque', 'cheque', 3),
--     (1, 'Tarjeta de credito', 'tarjeta_credito', 4),
--     (1, 'Deposito', 'deposito', 5),
--     (1, 'Debito bancario', 'debito_bancario', 6);
