from django.core.exceptions import ValidationError
from django.db import models


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


class Tema(models.Model):
    DIFICULTAD_CHOICES = (
        ("basica", "Basica"),
        ("media", "Media"),
        ("avanzada", "Avanzada"),
    )

    temario = models.ForeignKey(
        Temario,
        db_column="id_temario",
        on_delete=models.DO_NOTHING,
        related_name="temas",
    )
    nombre = models.CharField(max_length=180)
    orden = models.IntegerField(default=1)
    objetivo = models.TextField(blank=True, null=True)
    numero_clases = models.IntegerField(default=1)
    dificultad = models.CharField(max_length=20, choices=DIFICULTAD_CHOICES, default="media")
    meta_preguntas_proceso = models.IntegerField(default=10)
    meta_preguntas_final = models.IntegerField(default=10)
    activo = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    usuario_updated = models.ForeignKey(
        "auth.User",
        db_column="id_usuario_updated",
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
        related_name="temas_actualizados",
    )

    class Meta:
        db_table = '"academico"."tema"'
        unique_together = (("temario", "orden"),)
        ordering = ["temario", "orden"]

    def __str__(self):
        return self.nombre


class Subtema(models.Model):
    tema = models.ForeignKey(
        Tema,
        db_column="id_tema",
        on_delete=models.DO_NOTHING,
        related_name="subtemas",
    )
    nombre = models.CharField(max_length=180)
    orden = models.IntegerField(default=1)
    objetivo = models.TextField(blank=True, null=True)
    activo = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    usuario_updated = models.ForeignKey(
        "auth.User",
        db_column="id_usuario_updated",
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
        related_name="subtemas_actualizados",
    )

    class Meta:
        db_table = '"academico"."subtema"'
        unique_together = (("tema", "orden"),)
        ordering = ["tema", "orden"]

    def __str__(self):
        return self.nombre


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
    tipo_planificacion = models.CharField(max_length=120, blank=True, null=True)
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
        ("borrador", "Borrador"),
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
        Tema,
        db_column="id_tema",
        on_delete=models.DO_NOTHING,
    )
    subtema = models.ForeignKey(
        Subtema,
        db_column="id_subtema",
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
    )
    numero_clase = models.IntegerField(default=1)
    fecha_planificada = models.DateField()
    objetivo = models.TextField()
    actividades = models.TextField()
    recursos_previstos = models.TextField(blank=True, null=True)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default="borrador")
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

    def __str__(self):
        return f"{self.asignatura} - {self.tema} ({self.fecha_planificada})"


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
        Tema,
        db_column="id_tema",
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
    )
    subtema = models.ForeignKey(
        Subtema,
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
        Tema,
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
