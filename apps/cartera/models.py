from django.db import models


class FormaPago(models.Model):
    empresa = models.ForeignKey(
        "core.Empresa",
        db_column="id_empresa",
        on_delete=models.DO_NOTHING,
    )
    nombre = models.CharField(max_length=30)
    tipo = models.CharField(max_length=20, blank=True, null=True)
    activo = models.BooleanField(default=True)
    orden = models.IntegerField(blank=True, null=True)
    es_venta = models.BooleanField(default=True)
    es_pago = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    usuario_updated = models.ForeignKey(
        "auth.User",
        db_column="id_usuario_updated",
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
        related_name="formas_pago_actualizadas",
    )

    class Meta:
        db_table = '"cartera"."forma_pago"'
        unique_together = (("empresa", "tipo"),)
        ordering = ["orden", "nombre"]

    def __str__(self):
        return self.nombre


class PlanPago(models.Model):
    ESTADO_CHOICES = (
        ("borrador", "Borrador"),
        ("activo", "Activo"),
        ("cerrado", "Cerrado"),
        ("anulado", "Anulado"),
    )

    empresa = models.ForeignKey(
        "core.Empresa",
        db_column="id_empresa",
        on_delete=models.DO_NOTHING,
    )
    ficha_inscripcion = models.OneToOneField(
        "matricula.FichaInscripcion",
        db_column="id_ficha_inscripcion",
        on_delete=models.DO_NOTHING,
        related_name="plan_pago",
    )
    valor_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    valor_matricula = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    descuento = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    abono = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    saldo = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default="activo")
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
        related_name="planes_pago_actualizados",
    )

    class Meta:
        db_table = '"cartera"."plan_pago"'
        ordering = ["-created"]

    def __str__(self):
        return f"Plan {self.ficha_inscripcion}"


class Cuota(models.Model):
    ESTADO_CHOICES = (
        ("pendiente", "Pendiente"),
        ("parcial", "Parcial"),
        ("pagada", "Pagada"),
        ("vencida", "Vencida"),
        ("anulada", "Anulada"),
    )

    PRIORIDAD_CHOICES = (
        ("baja", "Baja"),
        ("normal", "Normal"),
        ("alta", "Alta"),
        ("critica", "Critica"),
    )

    plan_pago = models.ForeignKey(
        PlanPago,
        db_column="id_plan_pago",
        on_delete=models.DO_NOTHING,
        related_name="cuotas",
    )
    numero = models.IntegerField()
    fecha_pago_debito = models.DateField()
    valor = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    valor_pagado = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    numero_recibo_factura_deposito = models.CharField(max_length=60, blank=True, null=True)
    observacion = models.TextField(blank=True, null=True)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default="pendiente")
    prioridad = models.CharField(max_length=20, choices=PRIORIDAD_CHOICES, default="normal")
    activo = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    usuario_updated = models.ForeignKey(
        "auth.User",
        db_column="id_usuario_updated",
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
        related_name="cuotas_actualizadas",
    )

    class Meta:
        db_table = '"cartera"."cuota"'
        unique_together = (("plan_pago", "numero"),)
        ordering = ["fecha_pago_debito", "numero"]

    def __str__(self):
        return f"Cuota {self.numero} - {self.plan_pago}"

    def saldo(self):
        return self.valor - self.valor_pagado


class Pago(models.Model):
    empresa = models.ForeignKey(
        "core.Empresa",
        db_column="id_empresa",
        on_delete=models.DO_NOTHING,
    )
    cuota = models.ForeignKey(
        Cuota,
        db_column="id_cuota",
        on_delete=models.DO_NOTHING,
        related_name="pagos",
    )
    forma_pago = models.ForeignKey(
        FormaPago,
        db_column="id_forma_pago",
        on_delete=models.DO_NOTHING,
    )
    fecha_registro = models.DateTimeField()
    valor = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    numero_documento = models.CharField(max_length=60, blank=True, null=True)
    comprobante = models.FileField(upload_to="cartera/comprobantes/", blank=True, null=True)
    comentario = models.TextField(blank=True, null=True)
    usuario = models.ForeignKey(
        "auth.User",
        db_column="id_usuario",
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
        related_name="pagos_registrados",
    )
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    usuario_updated = models.ForeignKey(
        "auth.User",
        db_column="id_usuario_updated",
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
        related_name="pagos_actualizados",
    )

    class Meta:
        db_table = '"cartera"."pago"'
        ordering = ["-fecha_registro"]

    def __str__(self):
        return f"{self.valor} - {self.forma_pago}"
