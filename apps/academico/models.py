from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Asignatura(models.Model):
    empresa = models.ForeignKey(
        "core.Empresa",
        db_column="id_empresa",
        on_delete=models.DO_NOTHING,
    )
    codigo = models.CharField(max_length=40)
    nombre = models.CharField(max_length=160)
    activo = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    usuario_updated = models.ForeignKey(
        "auth.User",
        db_column="id_usuario_updated",
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
        related_name="asignaturas_actualizadas",
    )

    class Meta:
        db_table = '"academico"."asignatura"'
        unique_together = (("empresa", "codigo"),)
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Temario(models.Model):
    ESTADO_CHOICES = (
        ("borrador", "Borrador"),
        ("activo", "Activo"),
        ("archivado", "Archivado"),
    )

    empresa = models.ForeignKey(
        "core.Empresa",
        db_column="id_empresa",
        on_delete=models.DO_NOTHING,
    )
    periodo_academico = models.ForeignKey(
        "matricula.PeriodoAcademico",
        db_column="id_periodo_academico",
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
    )
    asignatura = models.ForeignKey(
        Asignatura,
        db_column="id_asignatura",
        on_delete=models.DO_NOTHING,
        related_name="temarios",
    )
    nombre = models.CharField(max_length=180)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default="borrador")
    activo = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    usuario_updated = models.ForeignKey(
        "auth.User",
        db_column="id_usuario_updated",
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
        related_name="temarios_actualizados",
    )

    class Meta:
        db_table = '"academico"."temario"'
        ordering = ["asignatura", "nombre"]

    def __str__(self):
        return f"{self.asignatura} - {self.nombre}"


class DocenteAsignatura(models.Model):
    empresa = models.ForeignKey(
        "core.Empresa",
        db_column="id_empresa",
        on_delete=models.DO_NOTHING,
    )
    docente = models.ForeignKey(
        "core.Partner",
        db_column="id_docente",
        on_delete=models.DO_NOTHING,
        related_name="docente_asignaturas",
    )
    asignatura = models.ForeignKey(
        Asignatura,
        db_column="id_asignatura",
        on_delete=models.DO_NOTHING,
    )
    periodo_academico = models.ForeignKey(
        "matricula.PeriodoAcademico",
        db_column="id_periodo_academico",
        on_delete=models.DO_NOTHING,
    )
    aula = models.ForeignKey(
        "matricula.Aula",
        db_column="id_aula",
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
    )
    activo = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    usuario_updated = models.ForeignKey(
        "auth.User",
        db_column="id_usuario_updated",
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
        related_name="docente_asignaturas_actualizadas",
    )

    class Meta:
        db_table = '"academico"."docente_asignatura"'
        ordering = ["periodo_academico", "asignatura", "docente"]

    def __str__(self):
        return f"{self.docente} - {self.asignatura}"


class HorarioClase(models.Model):
    ESTADO_CHOICES = (
        ("programada", "Programada"),
        ("realizada", "Realizada"),
        ("no_dio_clases", "No dio clases"),
        ("reprogramada", "Reprogramada"),
        ("cancelada", "Cancelada"),
    )

    empresa = models.ForeignKey(
        "core.Empresa",
        db_column="id_empresa",
        on_delete=models.DO_NOTHING,
    )
    periodo_academico = models.ForeignKey(
        "matricula.PeriodoAcademico",
        db_column="id_periodo_academico",
        on_delete=models.DO_NOTHING,
        related_name="horarios_clase",
    )
    aula = models.ForeignKey(
        "matricula.Aula",
        db_column="id_aula",
        on_delete=models.DO_NOTHING,
        related_name="horarios_clase",
    )
    asignatura = models.ForeignKey(
        Asignatura,
        db_column="id_asignatura",
        on_delete=models.DO_NOTHING,
        related_name="horarios_clase",
    )
    docente = models.ForeignKey(
        "core.Partner",
        db_column="id_docente",
        on_delete=models.DO_NOTHING,
        related_name="horarios_docente",
    )
    fecha = models.DateField()
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    tutor = models.ForeignKey(
        "core.Partner",
        db_column="id_tutor",
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
        related_name="horarios_tutor",
    )
    tema_previsto = models.TextField(blank=True, null=True)
    observacion = models.TextField(blank=True, null=True)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default="programada")
    activo = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    usuario_updated = models.ForeignKey(
        "auth.User",
        db_column="id_usuario_updated",
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
        related_name="horarios_clase_actualizados",
    )

    class Meta:
        db_table = '"academico"."horario_clase"'
        ordering = ["fecha", "hora_inicio", "aula", "asignatura"]
        unique_together = (("periodo_academico", "aula", "fecha", "hora_inicio", "hora_fin"),)
        permissions = (("view_all_horarioclase", "Puede ver todos los horarios"),)

    def clean(self):
        super().clean()
        if self.hora_inicio and self.hora_fin and self.hora_inicio >= self.hora_fin:
            raise ValidationError({"hora_fin": "La hora fin debe ser mayor que la hora inicio."})

        if not self.fecha or not self.hora_inicio or not self.hora_fin:
            return

        overlapping = HorarioClase.objects.filter(
            fecha=self.fecha,
            activo=True,
            hora_inicio__lt=self.hora_fin,
            hora_fin__gt=self.hora_inicio,
        ).exclude(pk=self.pk)
        if self.aula_id and overlapping.filter(aula_id=self.aula_id).exists():
            raise ValidationError("Ya existe una clase en esa aula dentro del mismo horario.")
        if self.docente_id and overlapping.filter(docente_id=self.docente_id).exists():
            raise ValidationError("El docente ya tiene otra clase dentro del mismo horario.")

    def __str__(self):
        return f"{self.fecha} {self.hora_inicio}-{self.hora_fin} {self.aula} {self.asignatura}"


class PlanificacionClase(models.Model):
    ESTADO_CHOICES = (
        ("pendiente", "Pendiente"),
        ("revision", "En revision"),
        ("aprobada", "Aprobada"),
        ("rechazada", "Rechazada"),
        ("completada", "Completada"),
    )

    empresa = models.ForeignKey(
        "core.Empresa",
        db_column="id_empresa",
        on_delete=models.DO_NOTHING,
    )
    horario_clase = models.OneToOneField(
        HorarioClase,
        db_column="id_horario_clase",
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
        related_name="planificacion",
    )
    docente = models.ForeignKey(
        "core.Partner",
        db_column="id_docente",
        on_delete=models.DO_NOTHING,
        related_name="planificaciones_docente",
    )
    aula = models.ForeignKey(
        "matricula.Aula",
        db_column="id_aula",
        on_delete=models.DO_NOTHING,
    )
    asignatura = models.ForeignKey(
        Asignatura,
        db_column="id_asignatura",
        on_delete=models.DO_NOTHING,
    )
    tema = models.ForeignKey(
        "academico.Tema",
        db_column="id_tema",
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
    )
    subtema = models.ForeignKey(
        "academico.Subtema",
        db_column="id_subtema",
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
    )
    numero_clase = models.IntegerField(default=1)
    fecha_planificada = models.DateField()
    objetivo = models.TextField(blank=True, null=True)
    competencias = models.TextField(blank=True, null=True)
    estrategias = models.TextField(blank=True, null=True)
    actividades = models.TextField(blank=True, null=True)
    recursos_previstos = models.TextField(blank=True, null=True)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default="pendiente")
    revisado_por = models.ForeignKey(
        "core.Partner",
        db_column="id_revisado_por",
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
        related_name="planificaciones_revisadas",
    )
    fecha_revision = models.DateTimeField(blank=True, null=True)
    notas_revision = models.TextField(blank=True, null=True)
    activo = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    usuario_updated = models.ForeignKey(
        "auth.User",
        db_column="id_usuario_updated",
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
        related_name="planificaciones_actualizadas",
    )

    class Meta:
        db_table = '"academico"."planificacion_clase"'
        ordering = ["fecha_planificada", "aula", "numero_clase"]
        permissions = (("review_planificacionclase", "Puede revisar planificaciones de clase"),)

    def __str__(self):
        return f"{self.asignatura} ({self.fecha_planificada})"


class RecursoClase(models.Model):
    TIPO_CHOICES = (
        ("documento", "Documento"),
        ("video", "Video"),
        ("enlace", "Enlace"),
        ("diapositiva", "Diapositiva"),
        ("otro", "Otro"),
    )

    planificacion_clase = models.ForeignKey(
        PlanificacionClase,
        db_column="id_planificacion_clase",
        on_delete=models.DO_NOTHING,
        related_name="recursos",
    )
    titulo = models.CharField(max_length=180)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default="documento")
    url = models.TextField(blank=True, null=True)
    archivo = models.FileField(upload_to="academico/recursos/", blank=True, null=True)
    listo = models.BooleanField(default=False)
    creado_por = models.ForeignKey(
        "core.Partner",
        db_column="id_creado_por",
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
    )
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    usuario_updated = models.ForeignKey(
        "auth.User",
        db_column="id_usuario_updated",
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
        related_name="recursos_clase_actualizados",
    )

    class Meta:
        db_table = '"academico"."recurso_clase"'
        ordering = ["titulo"]

    def __str__(self):
        return self.titulo


class BancoPregunta(models.Model):
    TIPO_CHOICES = (
        ("proceso", "Proceso"),
        ("final", "Simulador/final"),
    )

    empresa = models.ForeignKey(
        "core.Empresa",
        db_column="id_empresa",
        on_delete=models.DO_NOTHING,
    )
    asignatura = models.ForeignKey(
        Asignatura,
        db_column="id_asignatura",
        on_delete=models.DO_NOTHING,
    )
    tema = models.ForeignKey(
        "academico.Tema",
        db_column="id_tema",
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
    )
    subtema = models.ForeignKey(
        "academico.Subtema",
        db_column="id_subtema",
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
    )
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    meta_preguntas = models.IntegerField(default=10)
    revisado_coordinacion = models.BooleanField(default=False)
    activo = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    usuario_updated = models.ForeignKey(
        "auth.User",
        db_column="id_usuario_updated",
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
        related_name="bancos_pregunta_actualizados",
    )

    class Meta:
        db_table = '"academico"."banco_pregunta"'
        ordering = ["asignatura", "tema", "tipo"]

    def __str__(self):
        return f"{self.asignatura} - {self.get_tipo_display()}"


class Pregunta(models.Model):
    DIFICULTAD_CHOICES = (
        ("facil", "Facil"),
        ("media", "Media"),
        ("dificil", "Dificil"),
    )

    ESTADO_CHOICES = (
        ("borrador", "Borrador"),
        ("revision", "En revision"),
        ("aprobada", "Aprobada"),
        ("rechazada", "Rechazada"),
    )

    banco_pregunta = models.ForeignKey(
        BancoPregunta,
        db_column="id_banco_pregunta",
        on_delete=models.DO_NOTHING,
        related_name="preguntas",
    )
    creado_por = models.ForeignKey(
        "core.Partner",
        db_column="id_creado_por",
        on_delete=models.DO_NOTHING,
        related_name="preguntas_creadas",
    )
    enunciado = models.TextField()
    respuestas = models.JSONField(default=list, blank=True)
    respuesta_correcta = models.TextField(blank=True, null=True)
    explicacion = models.TextField(blank=True, null=True)
    dificultad = models.CharField(max_length=20, choices=DIFICULTAD_CHOICES, default="media")
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default="borrador")
    revisado_por = models.ForeignKey(
        "core.Partner",
        db_column="id_revisado_por",
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
        related_name="preguntas_revisadas",
    )
    fecha_revision = models.DateTimeField(blank=True, null=True)
    notas_revision = models.TextField(blank=True, null=True)
    activo = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    usuario_updated = models.ForeignKey(
        "auth.User",
        db_column="id_usuario_updated",
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
        related_name="preguntas_actualizadas",
    )

    class Meta:
        db_table = '"academico"."pregunta"'
        ordering = ["banco_pregunta", "-created"]

    def __str__(self):
        return self.enunciado[:80]


class Asistencia(models.Model):
    ESTADO_CHOICES = (
        ("presente", "Presente"),
        ("ausente", "Ausente"),
        ("atraso", "Atraso"),
        ("justificado", "Justificado"),
    )

    planificacion_clase = models.ForeignKey(
        PlanificacionClase,
        db_column="id_planificacion_clase",
        on_delete=models.DO_NOTHING,
        related_name="asistencias",
    )
    estudiante = models.ForeignKey(
        "core.Partner",
        db_column="id_estudiante",
        on_delete=models.DO_NOTHING,
        related_name="asistencias",
    )
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES)
    observacion = models.TextField(blank=True, null=True)
    registrado_por = models.ForeignKey(
        "core.Partner",
        db_column="id_registrado_por",
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
    )
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    usuario_updated = models.ForeignKey(
        "auth.User",
        db_column="id_usuario_updated",
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
        related_name="asistencias_actualizadas",
    )

    class Meta:
        db_table = '"academico"."asistencia"'
        unique_together = (("planificacion_clase", "estudiante"),)
        ordering = ["planificacion_clase", "estudiante"]

    def __str__(self):
        return f"{self.estudiante} - {self.estado}"


class Evaluacion(models.Model):
    TIPO_CHOICES = (
        ("proceso", "Proceso"),
        ("final", "Final"),
        ("simulador", "Simulador"),
    )

    empresa = models.ForeignKey(
        "core.Empresa",
        db_column="id_empresa",
        on_delete=models.DO_NOTHING,
    )
    planificacion_clase = models.ForeignKey(
        PlanificacionClase,
        db_column="id_planificacion_clase",
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
    )
    asignatura = models.ForeignKey(
        Asignatura,
        db_column="id_asignatura",
        on_delete=models.DO_NOTHING,
    )
    tema = models.ForeignKey(
        "academico.Tema",
        db_column="id_tema",
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
    )
    titulo = models.CharField(max_length=180)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default="proceso")
    fecha = models.DateField()
    puntaje_maximo = models.DecimalField(max_digits=5, decimal_places=2, default=10)
    creado_por = models.ForeignKey(
        "core.Partner",
        db_column="id_creado_por",
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
    )
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    usuario_updated = models.ForeignKey(
        "auth.User",
        db_column="id_usuario_updated",
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
        related_name="evaluaciones_actualizadas",
    )

    class Meta:
        db_table = '"academico"."evaluacion"'
        ordering = ["-fecha", "asignatura"]

    def __str__(self):
        return self.titulo


class EvaluacionResultado(models.Model):
    evaluacion = models.ForeignKey(
        Evaluacion,
        db_column="id_evaluacion",
        on_delete=models.DO_NOTHING,
        related_name="resultados",
    )
    estudiante = models.ForeignKey(
        "core.Partner",
        db_column="id_estudiante",
        on_delete=models.DO_NOTHING,
        related_name="evaluacion_resultados",
    )
    nota = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    observacion = models.TextField(blank=True, null=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    usuario_updated = models.ForeignKey(
        "auth.User",
        db_column="id_usuario_updated",
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
        related_name="evaluacion_resultados_actualizados",
    )

    class Meta:
        db_table = '"academico"."evaluacion_resultado"'
        unique_together = (("evaluacion", "estudiante"),)
        ordering = ["evaluacion", "estudiante"]

    def __str__(self):
        return f"{self.estudiante} - {self.nota}"


class Curso(models.Model):
    id = models.BigAutoField(primary_key=True)
    nombre = models.CharField(max_length=150)
    activo = models.BooleanField(default=True)
    descripcion = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    usuario_updated = models.ForeignKey(
        "auth.User",
        db_column="id_usuario_updated",
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
        related_name="academico_cursos_actualizados",
    )

    class Meta:
        db_table = '"academico"."curso"'
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Aula(models.Model):
    id = models.BigAutoField(primary_key=True)
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True, null=True)

    class Meta:
        db_table = '"academico"."aula"'
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class AulaCurso(models.Model):
    id = models.BigAutoField(primary_key=True)
    aula = models.ForeignKey(
        Aula,
        db_column="id_aula",
        on_delete=models.RESTRICT,
        related_name="aula_cursos",
    )
    curso = models.ForeignKey(
        Curso,
        db_column="id_curso",
        on_delete=models.RESTRICT,
        related_name="aula_cursos",
    )
    nombre = models.CharField(max_length=150, blank=True, null=True)
    descripcion = models.TextField(blank=True, null=True)

    class Meta:
        db_table = '"academico"."aula_curso"'
        unique_together = (("aula", "curso"),)
        ordering = ["aula", "curso"]

    def __str__(self):
        return self.nombre or f"{self.aula} - {self.curso}"


class Dia(models.Model):
    id = models.BigAutoField(primary_key=True)
    dia = models.CharField(max_length=20, unique=True)

    class Meta:
        db_table = '"academico"."dia"'
        ordering = ["id"]

    def __str__(self):
        return self.dia


class Horario(models.Model):
    id = models.BigAutoField(primary_key=True)
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()

    class Meta:
        db_table = '"academico"."horario"'
        ordering = ["hora_inicio", "hora_fin"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(hora_fin__gt=models.F("hora_inicio")),
                name="chk_horario_horas",
            ),
        ]

    def clean(self):
        super().clean()
        if self.hora_inicio and self.hora_fin and self.hora_fin <= self.hora_inicio:
            raise ValidationError({"hora_fin": "La hora fin debe ser mayor que la hora inicio."})

    def __str__(self):
        return f"{self.hora_inicio} - {self.hora_fin}"


class HorarioDia(models.Model):
    id = models.BigAutoField(primary_key=True)
    dia = models.ForeignKey(
        Dia,
        db_column="id_dia",
        on_delete=models.CASCADE,
        related_name="horario_dias",
    )
    horario = models.ForeignKey(
        Horario,
        db_column="id_horario",
        on_delete=models.CASCADE,
        related_name="horario_dias",
    )

    class Meta:
        db_table = '"academico"."horario_dia"'
        unique_together = (("dia", "horario"),)
        ordering = ["dia", "horario"]

    def __str__(self):
        return f"{self.dia} {self.horario}"


class HorarioAulaCurso(models.Model):
    id = models.BigAutoField(primary_key=True)
    aula_curso = models.ForeignKey(
        AulaCurso,
        db_column="id_aula_curso",
        on_delete=models.CASCADE,
        related_name="horario_aula_cursos",
    )
    horario_dia = models.ForeignKey(
        HorarioDia,
        db_column="id_horario_dia",
        on_delete=models.CASCADE,
        related_name="horario_aula_cursos",
    )
    fecha = models.DateField(blank=True, null=True)

    class Meta:
        db_table = '"academico"."horario_aula_curso"'
        ordering = ["aula_curso", "horario_dia", "fecha"]
        constraints = [
            models.UniqueConstraint(
                fields=["aula_curso", "horario_dia"],
                condition=models.Q(fecha__isnull=True),
                name="uq_horario_aula_curso_periodo",
            ),
            models.UniqueConstraint(
                fields=["aula_curso", "horario_dia", "fecha"],
                condition=models.Q(fecha__isnull=False),
                name="uq_horario_aula_curso_fecha",
            ),
        ]

    def __str__(self):
        return f"{self.aula_curso} - {self.horario_dia}"


class Materia(models.Model):
    id = models.BigAutoField(primary_key=True)
    nombre = models.CharField(max_length=150)
    nombre_corto = models.CharField(max_length=50, blank=True, null=True)
    color = models.CharField(max_length=7, default="#2563eb")
    descripcion = models.TextField(blank=True, null=True)

    class Meta:
        db_table = '"academico"."materia"'
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class MateriaCurso(models.Model):
    id = models.BigAutoField(primary_key=True)
    materia = models.ForeignKey(
        Materia,
        db_column="id_materia",
        on_delete=models.RESTRICT,
        related_name="materia_cursos",
    )
    grupo = models.ForeignKey(
        Curso,
        db_column="id_grupo",
        on_delete=models.CASCADE,
        related_name="materia_cursos",
    )

    class Meta:
        db_table = '"academico"."materia_curso"'
        unique_together = (("materia", "grupo"),)
        ordering = ["grupo", "materia"]

    def __str__(self):
        return f"{self.grupo} - {self.materia}"


class MateriaHorario(models.Model):
    id = models.BigAutoField(primary_key=True)
    materia_grupo = models.ForeignKey(
        MateriaCurso,
        db_column="id_materia_grupo",
        on_delete=models.CASCADE,
        related_name="materia_horarios",
    )
    horario_aula_curso = models.ForeignKey(
        HorarioAulaCurso,
        db_column="id_horario_aula_curso",
        on_delete=models.CASCADE,
        related_name="materia_horarios",
    )

    class Meta:
        db_table = '"academico"."materia_horario"'
        unique_together = (("materia_grupo", "horario_aula_curso"),)
        ordering = ["materia_grupo", "horario_aula_curso"]

    def __str__(self):
        return f"{self.materia_grupo} - {self.horario_aula_curso}"


class Periodo(models.Model):
    id = models.BigAutoField(primary_key=True)
    nombre = models.CharField(max_length=150)
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()

    class Meta:
        db_table = '"academico"."periodo"'
        ordering = ["-fecha_inicio", "nombre"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(fecha_fin__gte=models.F("fecha_inicio")),
                name="chk_periodo_fechas",
            ),
        ]

    def clean(self):
        super().clean()
        if self.fecha_inicio and self.fecha_fin and self.fecha_fin < self.fecha_inicio:
            raise ValidationError({"fecha_fin": "La fecha fin debe ser mayor o igual que la fecha inicio."})

    def __str__(self):
        return self.nombre


class CursoPeriodo(models.Model):
    id = models.BigAutoField(primary_key=True)
    curso = models.ForeignKey(
        Curso,
        db_column="id_curso",
        on_delete=models.CASCADE,
        related_name="curso_periodos",
    )
    periodo = models.ForeignKey(
        Periodo,
        db_column="id_periodo",
        on_delete=models.RESTRICT,
        related_name="curso_periodos",
    )

    class Meta:
        db_table = '"academico"."curso_periodo"'
        unique_together = (("curso", "periodo"),)
        ordering = ["periodo", "curso"]

    def __str__(self):
        return f"{self.curso} - {self.periodo}"


class Clase(models.Model):
    ESTADO_PLANIFICACION_CHOICES = (
        ("pendiente", "Pendiente"),
        ("revision", "En revision"),
        ("aprobada", "Aprobada"),
        ("rechazada", "Rechazada"),
    )

    id = models.BigAutoField(primary_key=True)
    horario_aula_curso = models.ForeignKey(
        HorarioAulaCurso,
        db_column="id_horario_aula_curso",
        on_delete=models.CASCADE,
        related_name="clases",
    )
    materia_curso = models.ForeignKey(
        MateriaCurso,
        db_column="id_materia_curso",
        on_delete=models.RESTRICT,
        related_name="clases",
    )
    docente = models.ForeignKey(
        "core.Partner",
        db_column="id_docente",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="clases_asignadas",
    )
    fecha = models.DateField()
    tema = models.ForeignKey(
        "academico.Tema",
        db_column="id_tema",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="clases",
    )
    subtema = models.ForeignKey(
        "academico.Subtema",
        db_column="id_subtema",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="clases",
    )
    descripcion = models.TextField(blank=True, null=True)
    competencias = models.ManyToManyField(
        "academico.Competencia",
        blank=True,
        related_name="clases",
    )
    estrategias = models.ManyToManyField(
        "academico.Estrategia",
        blank=True,
        related_name="clases",
    )
    recursos = models.ManyToManyField(
        "academico.Recurso",
        through="academico.ClaseRecurso",
        blank=True,
        related_name="clases",
    )
    revision_tema_ok = models.BooleanField(default=False)
    revision_detalle_ok = models.BooleanField(default=False)
    revision_competencias_ok = models.BooleanField(default=False)
    revision_estrategias_ok = models.BooleanField(default=False)
    revision_recursos_ok = models.BooleanField(default=False)
    estado_planificacion = models.CharField(
        max_length=20,
        choices=ESTADO_PLANIFICACION_CHOICES,
        default="pendiente",
    )
    notas_revision = models.TextField(blank=True, null=True)
    observaciones_revision = models.JSONField(default=dict, blank=True)
    revisado_por = models.ForeignKey(
        "core.Partner",
        db_column="id_revisado_por",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="clases_revisadas",
    )
    fecha_revision = models.DateTimeField(blank=True, null=True)
    asistencia_cerrada = models.BooleanField(default=False)
    asistencia_cerrada_por = models.ForeignKey(
        "core.Partner",
        db_column="id_asistencia_cerrada_por",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="clases_asistencia_cerradas",
    )
    fecha_cierre_asistencia = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = '"academico"."clase"'
        unique_together = (("horario_aula_curso", "fecha"),)
        ordering = ["fecha", "horario_aula_curso"]

    def __str__(self):
        return f"{self.fecha} - {self.horario_aula_curso} - {self.materia_curso}"


class ClaseRecurso(models.Model):
    id = models.BigAutoField(primary_key=True)
    clase = models.ForeignKey(
        Clase,
        db_column="id_clase",
        on_delete=models.CASCADE,
        related_name="clase_recursos",
    )
    recurso = models.ForeignKey(
        "academico.Recurso",
        db_column="id_recurso",
        on_delete=models.CASCADE,
        related_name="clase_recursos",
    )
    archivo = models.FileField(upload_to="academico/clase_recursos/", blank=True, null=True)

    class Meta:
        db_table = '"academico"."clase_recurso"'
        unique_together = (("clase", "recurso"),)
        ordering = ["clase", "recurso"]

    def __str__(self):
        return f"{self.clase} - {self.recurso}"


class ProfesorMateriaCurso(models.Model):
    id = models.BigAutoField(primary_key=True)
    partner = models.ForeignKey(
        "core.Partner",
        db_column="id_partner",
        on_delete=models.RESTRICT,
        related_name="profesor_materia_cursos",
    )
    materia_curso = models.ForeignKey(
        MateriaCurso,
        db_column="id_materia_curso",
        on_delete=models.CASCADE,
        related_name="profesor_materia_cursos",
    )

    class Meta:
        db_table = '"academico"."profesor_materia_curso"'
        unique_together = (("partner", "materia_curso"),)
        ordering = ["materia_curso", "partner"]

    def __str__(self):
        return f"{self.partner} - {self.materia_curso}"


class GrupoEstudiante(models.Model):
    ESTADO_CHOICES = (
        ("activo", "Activo"),
        ("retirado", "Retirado"),
    )

    id = models.BigAutoField(primary_key=True)
    ficha_inscripcion = models.OneToOneField(
        "matricula.FichaInscripcion",
        db_column="id_ficha_inscripcion",
        on_delete=models.CASCADE,
        related_name="asignacion_grupo",
    )
    estudiante = models.ForeignKey(
        "core.Partner",
        db_column="id_estudiante",
        on_delete=models.RESTRICT,
        related_name="grupo_asignaciones",
    )
    grupo = models.ForeignKey(
        Curso,
        db_column="id_grupo",
        on_delete=models.CASCADE,
        related_name="estudiantes_asignados",
    )
    fecha_asignacion = models.DateField(default=timezone.localdate)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default="activo")
    observacion = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    usuario_updated = models.ForeignKey(
        "auth.User",
        db_column="id_usuario_updated",
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
        related_name="grupo_estudiantes_actualizados",
    )

    class Meta:
        db_table = '"academico"."grupo_estudiante"'
        ordering = ["grupo", "estudiante__nombre"]

    def clean(self):
        super().clean()
        if self.estudiante_id and not self.estudiante.es_estudiante:
            raise ValidationError({"estudiante": "Solo se pueden asignar estudiantes."})
        if (
            self.ficha_inscripcion_id
            and self.estudiante_id
            and self.ficha_inscripcion.estudiante_id != self.estudiante_id
        ):
            raise ValidationError({"estudiante": "El estudiante debe coincidir con la ficha seleccionada."})

    def save(self, *args, **kwargs):
        if self.ficha_inscripcion_id and not self.estudiante_id:
            self.estudiante = self.ficha_inscripcion.estudiante
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.estudiante} - {self.grupo}"


class ClaseEstudianteMovimiento(models.Model):
    id = models.BigAutoField(primary_key=True)
    asignacion = models.ForeignKey(
        GrupoEstudiante,
        db_column="id_grupo_estudiante",
        on_delete=models.CASCADE,
        related_name="movimientos_clase",
    )
    clase_origen = models.ForeignKey(
        Clase,
        db_column="id_clase_origen",
        on_delete=models.CASCADE,
        related_name="movimientos_salida",
    )
    clase_destino = models.ForeignKey(
        Clase,
        db_column="id_clase_destino",
        on_delete=models.CASCADE,
        related_name="movimientos_entrada",
    )
    fecha_inicio = models.DateField(default=timezone.localdate)
    motivo = models.TextField(blank=True, null=True)
    activo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    usuario_updated = models.ForeignKey(
        "auth.User",
        db_column="id_usuario_updated",
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
        related_name="movimientos_clase_actualizados",
    )

    class Meta:
        db_table = '"academico"."clase_estudiante_movimiento"'
        unique_together = (("asignacion", "clase_origen"),)
        ordering = ["-created_at"]

    def clean(self):
        super().clean()
        if self.clase_origen_id and self.clase_destino_id and self.clase_origen_id == self.clase_destino_id:
            raise ValidationError({"clase_destino": "La clase destino debe ser distinta a la clase origen."})
        if not self.asignacion_id or not self.clase_origen_id or not self.clase_destino_id:
            return
        if self.clase_origen.materia_curso.materia_id != self.clase_destino.materia_curso.materia_id:
            raise ValidationError({"clase_destino": "Solo puedes mover entre grupos que tengan la misma materia."})
        if self.clase_origen.materia_curso_id == self.clase_destino.materia_curso_id:
            raise ValidationError({"clase_destino": "Selecciona una clase destino de otro grupo."})
        if self.clase_origen.materia_curso.grupo_id != self.asignacion.grupo_id:
            raise ValidationError({"clase_origen": "La clase origen no pertenece al grupo del estudiante."})
        if self.activo:
            active_duplicates = ClaseEstudianteMovimiento.objects.filter(
                asignacion=self.asignacion,
                clase_origen__materia_curso=self.clase_origen.materia_curso,
                activo=True,
            ).exclude(pk=self.pk)
            if active_duplicates.exists():
                raise ValidationError({"clase_origen": "El estudiante ya tiene un cambio activo para esta materia."})

    def __str__(self):
        return f"{self.asignacion.estudiante} - {self.clase_origen} -> {self.clase_destino}"


class ClaseAsistencia(models.Model):
    ESTADO_CHOICES = Asistencia.ESTADO_CHOICES

    id = models.BigAutoField(primary_key=True)
    clase = models.ForeignKey(
        Clase,
        db_column="id_clase",
        on_delete=models.CASCADE,
        related_name="asistencias_clase",
    )
    estudiante = models.ForeignKey(
        "core.Partner",
        db_column="id_estudiante",
        on_delete=models.RESTRICT,
        related_name="asistencias_clase",
    )
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default="presente")
    observacion = models.TextField(blank=True, null=True)
    registrado_por = models.ForeignKey(
        "core.Partner",
        db_column="id_registrado_por",
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
        related_name="asistencias_clase_registradas",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    usuario_updated = models.ForeignKey(
        "auth.User",
        db_column="id_usuario_updated",
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
        related_name="asistencias_clase_actualizadas",
    )

    class Meta:
        db_table = '"academico"."clase_asistencia"'
        unique_together = (("clase", "estudiante"),)
        ordering = ["clase", "estudiante__nombre"]

    def __str__(self):
        return f"{self.clase} - {self.estudiante} - {self.estado}"


class PlanificacionDocente(models.Model):
    id = models.BigAutoField(primary_key=True)
    materia_curso = models.ForeignKey(
        MateriaCurso,
        db_column="id_materia_curso",
        on_delete=models.CASCADE,
        related_name="planificaciones",
    )
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = '"academico"."planificacion"'
        ordering = ["materia_curso", "nombre"]

    def __str__(self):
        return self.nombre


class Tema(models.Model):
    id = models.BigAutoField(primary_key=True)
    planificacion = models.ForeignKey(
        PlanificacionDocente,
        db_column="id_planificacion",
        on_delete=models.CASCADE,
        related_name="temas_planificacion",
    )
    nombre = models.CharField(max_length=200)
    detalle = models.TextField(blank=True, null=True)
    orden = models.IntegerField(default=1)

    class Meta:
        db_table = '"academico"."tema"'
        ordering = ["planificacion", "orden", "nombre"]

    def __str__(self):
        return self.nombre


class Subtema(models.Model):
    id = models.BigAutoField(primary_key=True)
    tema = models.ForeignKey(
        "academico.Tema",
        db_column="id_tema",
        on_delete=models.CASCADE,
        related_name="subtemas_planificacion",
    )
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True, null=True)
    orden = models.IntegerField(default=1)

    class Meta:
        db_table = '"academico"."subtema"'
        ordering = ["tema", "orden", "nombre"]

    def __str__(self):
        return self.nombre


class Competencia(models.Model):
    id = models.BigAutoField(primary_key=True)
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True, null=True)

    class Meta:
        db_table = '"academico"."competencia"'
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class PlanificacionCompetencia(models.Model):
    id = models.BigAutoField(primary_key=True)
    planificacion = models.ForeignKey(
        PlanificacionDocente,
        db_column="id_planificacion",
        on_delete=models.CASCADE,
        related_name="competencias_planificacion",
    )
    competencia = models.ForeignKey(
        Competencia,
        db_column="id_competencia",
        on_delete=models.RESTRICT,
        related_name="planificaciones_competencia",
    )

    class Meta:
        db_table = '"academico"."planificacion_competencia"'
        unique_together = (("planificacion", "competencia"),)
        ordering = ["planificacion", "competencia"]

    def __str__(self):
        return f"{self.planificacion} - {self.competencia}"


class ClasePlanificacion(models.Model):
    id = models.BigAutoField(primary_key=True)
    planificacion = models.ForeignKey(
        PlanificacionDocente,
        db_column="id_planificacion",
        on_delete=models.CASCADE,
        related_name="clases_planificacion",
    )
    numero = models.IntegerField()
    nombre = models.CharField(max_length=200, blank=True, null=True)
    descripcion = models.TextField(blank=True, null=True)
    orden = models.IntegerField(default=1)

    class Meta:
        db_table = '"academico"."clase_planificacion"'
        unique_together = (("planificacion", "numero"),)
        ordering = ["planificacion", "orden", "numero"]

    def __str__(self):
        return self.nombre or f"Clase {self.numero}"


class Estrategia(models.Model):
    id = models.BigAutoField(primary_key=True)
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True, null=True)

    class Meta:
        db_table = '"academico"."estrategia"'
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class ClaseEstrategia(models.Model):
    id = models.BigAutoField(primary_key=True)
    clase_planificacion = models.ForeignKey(
        ClasePlanificacion,
        db_column="id_clase_planificacion",
        on_delete=models.CASCADE,
        related_name="estrategias_clase",
    )
    estrategia = models.ForeignKey(
        Estrategia,
        db_column="id_estrategia",
        on_delete=models.RESTRICT,
        related_name="clases_estrategia",
    )
    orden = models.IntegerField(default=1)

    class Meta:
        db_table = '"academico"."clase_estrategia"'
        unique_together = (("clase_planificacion", "estrategia"),)
        ordering = ["clase_planificacion", "orden", "estrategia"]

    def __str__(self):
        return f"{self.clase_planificacion} - {self.estrategia}"


class Recurso(models.Model):
    id = models.BigAutoField(primary_key=True)
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True, null=True)

    class Meta:
        db_table = '"academico"."recurso"'
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class PlanificacionRecurso(models.Model):
    id = models.BigAutoField(primary_key=True)
    planificacion = models.ForeignKey(
        PlanificacionDocente,
        db_column="id_planificacion",
        on_delete=models.CASCADE,
        related_name="recursos_planificacion",
    )
    recurso = models.ForeignKey(
        Recurso,
        db_column="id_recurso",
        on_delete=models.RESTRICT,
        related_name="planificaciones_recurso",
    )

    class Meta:
        db_table = '"academico"."planificacion_recurso"'
        unique_together = (("planificacion", "recurso"),)
        ordering = ["planificacion", "recurso"]

    def __str__(self):
        return f"{self.planificacion} - {self.recurso}"
