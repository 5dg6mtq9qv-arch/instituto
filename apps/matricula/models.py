from django.db import models


class PeriodoAcademico(models.Model):
    empresa = models.ForeignKey(
        "core.Empresa",
        db_column="id_empresa",
        on_delete=models.DO_NOTHING,
    )
    nombre = models.CharField(max_length=120)
    regimen = models.CharField(max_length=60, blank=True, null=True)
    fecha_inicio = models.DateField(blank=True, null=True)
    fecha_fin = models.DateField(blank=True, null=True)
    estado = models.CharField(max_length=20, default="borrador")
    activo = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    usuario_updated = models.ForeignKey(
        "auth.User",
        db_column="id_usuario_updated",
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
        related_name="periodos_actualizados",
    )

    class Meta:
        db_table = '"matricula"."periodo_academico"'
        unique_together = (("empresa", "nombre"),)
        ordering = ["-fecha_inicio", "nombre"]

    def __str__(self):
        return self.nombre


class Curso(models.Model):
    empresa = models.ForeignKey(
        "core.Empresa",
        db_column="id_empresa",
        on_delete=models.DO_NOTHING,
    )
    nombre = models.CharField(max_length=120)
    grado = models.CharField(max_length=60, blank=True, null=True)
    carrera = models.CharField(max_length=160, blank=True, null=True)
    universidad = models.CharField(max_length=160, blank=True, null=True)
    activo = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    usuario_updated = models.ForeignKey(
        "auth.User",
        db_column="id_usuario_updated",
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
        related_name="cursos_actualizados",
    )

    class Meta:
        db_table = '"matricula"."curso"'
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Aula(models.Model):
    empresa = models.ForeignKey(
        "core.Empresa",
        db_column="id_empresa",
        on_delete=models.DO_NOTHING,
    )
    periodo_academico = models.ForeignKey(
        PeriodoAcademico,
        db_column="id_periodo_academico",
        on_delete=models.DO_NOTHING,
    )
    nombre = models.CharField(max_length=120)
    seccion = models.CharField(max_length=40, blank=True, null=True)
    jornada = models.CharField(max_length=40, blank=True, null=True)
    horario = models.CharField(max_length=120, blank=True, null=True)
    hora = models.CharField(max_length=80, blank=True, null=True)
    duracion = models.CharField(max_length=80, blank=True, null=True)
    capacidad = models.IntegerField(default=0)
    activo = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    usuario_updated = models.ForeignKey(
        "auth.User",
        db_column="id_usuario_updated",
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
        related_name="aulas_actualizadas",
    )

    class Meta:
        db_table = '"matricula"."aula"'
        unique_together = (("periodo_academico", "nombre", "seccion"),)
        ordering = ["periodo_academico", "nombre", "seccion"]

    def __str__(self):
        return f"{self.nombre} {self.seccion or ''}".strip()


class FichaInscripcion(models.Model):
    FORMA_PAGO_CONVENIO_CHOICES = (
        ("quincenal", "Quincenal"),
        ("mensual", "Mensual"),
        ("unico", "Un solo pago total"),
    )

    ESTADO_CHOICES = (
        ("borrador", "Borrador"),
        ("activa", "Activa"),
        ("retirada", "Retirada"),
        ("finalizada", "Finalizada"),
        ("anulada", "Anulada"),
    )

    empresa = models.ForeignKey(
        "core.Empresa",
        db_column="id_empresa",
        on_delete=models.DO_NOTHING,
    )
    numero = models.CharField(max_length=30)
    fecha = models.DateField()
    periodo_academico = models.ForeignKey(
        PeriodoAcademico,
        db_column="id_periodo_academico",
        on_delete=models.DO_NOTHING,
    )
    curso = models.ForeignKey(
        Curso,
        db_column="id_curso",
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
    )
    aula = models.ForeignKey(
        Aula,
        db_column="id_aula",
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
    )
    cliente = models.ForeignKey(
        "core.Partner",
        db_column="id_cliente",
        on_delete=models.DO_NOTHING,
        related_name="fichas_cliente",
    )
    estudiante = models.ForeignKey(
        "core.Partner",
        db_column="id_estudiante",
        on_delete=models.DO_NOTHING,
        related_name="fichas_estudiante",
    )
    representante = models.ForeignKey(
        "core.Partner",
        db_column="id_representante",
        on_delete=models.DO_NOTHING,
        related_name="fichas_representante",
        blank=True,
        null=True,
    )
    edad = models.IntegerField(blank=True, null=True)
    colegio = models.CharField(max_length=200, blank=True, null=True)
    curso_grado = models.CharField(max_length=120, blank=True, null=True)
    nota_grado = models.CharField(max_length=60, blank=True, null=True)
    carrera = models.CharField(max_length=160, blank=True, null=True)
    universidad = models.CharField(max_length=160, blank=True, null=True)
    nombre_conyuge = models.CharField(max_length=200, blank=True, null=True)
    ocupacion_conyuge = models.CharField(max_length=120, blank=True, null=True)
    correo_estudiante = models.TextField(blank=True, null=True)
    correo_representante = models.TextField(blank=True, null=True)
    horario = models.CharField(max_length=120, blank=True, null=True)
    hora = models.CharField(max_length=80, blank=True, null=True)
    duracion = models.CharField(max_length=80, blank=True, null=True)
    forma_pago_convenio = models.CharField(
        max_length=20,
        choices=FORMA_PAGO_CONVENIO_CHOICES,
        blank=True,
        null=True,
    )
    fecha_proximo_pago = models.DateField(blank=True, null=True)
    valor_proximo_pago = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    valor_total_curso = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    valor_matricula = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    descuento = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    abono = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    saldo = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    promo = models.BooleanField(default=False)
    autorizacion_imagen = models.BooleanField(default=False)
    acepta_garantia = models.BooleanField(default=False)
    acepta_no_devolucion = models.BooleanField(default=False)
    firma_representante = models.TextField(blank=True, null=True)
    ci_representante_firma = models.CharField(max_length=20, blank=True, null=True)
    firma_director_asesor = models.TextField(blank=True, null=True)
    ci_director_asesor = models.CharField(max_length=20, blank=True, null=True)
    archivo_contrato = models.FileField(upload_to="matricula/contratos/", blank=True, null=True)
    archivo_ficha_firmada = models.FileField(upload_to="matricula/fichas/", blank=True, null=True)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default="borrador")
    observacion = models.TextField(blank=True, null=True)
    activo = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    usuario_updated = models.ForeignKey(
        "auth.User",
        db_column="id_usuario_updated",
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
        related_name="fichas_actualizadas",
    )

    class Meta:
        db_table = '"matricula"."ficha_inscripcion"'
        unique_together = (("empresa", "numero"),)
        ordering = ["-fecha", "-id"]

    def __str__(self):
        return f"{self.numero} - {self.estudiante}"


class AulaHistorial(models.Model):
    ficha_inscripcion = models.ForeignKey(
        FichaInscripcion,
        db_column="id_ficha_inscripcion",
        on_delete=models.DO_NOTHING,
        related_name="aula_historial",
    )
    aula_origen = models.ForeignKey(
        Aula,
        db_column="id_aula_origen",
        on_delete=models.DO_NOTHING,
        related_name="historial_origen",
        blank=True,
        null=True,
    )
    aula_destino = models.ForeignKey(
        Aula,
        db_column="id_aula_destino",
        on_delete=models.DO_NOTHING,
        related_name="historial_destino",
    )
    fecha_cambio = models.DateTimeField(auto_now_add=True)
    motivo = models.TextField(blank=True, null=True)
    usuario = models.ForeignKey(
        "auth.User",
        db_column="id_usuario",
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
        related_name="cambios_aula",
    )

    class Meta:
        db_table = '"matricula"."aula_historial"'
        ordering = ["-fecha_cambio"]

    def __str__(self):
        return f"{self.ficha_inscripcion} -> {self.aula_destino}"
