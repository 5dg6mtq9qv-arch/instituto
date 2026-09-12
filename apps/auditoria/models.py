from django.db import models


class LogAccion(models.Model):
    ACCION_CHOICES = (
        ("crear", "Crear"),
        ("actualizar", "Actualizar"),
        ("eliminar", "Eliminar"),
        ("ingreso", "Ingreso"),
        ("exportar", "Exportar"),
        ("aprobar", "Aprobar"),
        ("rechazar", "Rechazar"),
    )

    empresa = models.ForeignKey(
        "core.Empresa",
        db_column="id_empresa",
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
    )
    usuario = models.ForeignKey(
        "auth.User",
        db_column="id_usuario",
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
    )
    accion = models.CharField(max_length=20, choices=ACCION_CHOICES)
    modelo = models.CharField(max_length=120)
    object_id = models.CharField(max_length=80, blank=True, null=True)
    object_repr = models.CharField(max_length=255, blank=True, null=True)
    cambios = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True, null=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = '"auditoria"."log_accion"'
        ordering = ["-created"]

    def __str__(self):
        return f"{self.accion} {self.modelo} {self.object_id or ''}".strip()


class PagoAuditoria(models.Model):
    ACCION_CHOICES = (
        ("crear", "Creación"),
        ("modificar", "Modificación"),
    )

    accion = models.CharField(max_length=20, choices=ACCION_CHOICES)
    pago_id = models.PositiveBigIntegerField(db_index=True)
    empresa_id = models.PositiveBigIntegerField(blank=True, null=True, db_index=True)
    cuota_id = models.PositiveBigIntegerField(blank=True, null=True, db_index=True)
    plan_pago_id = models.PositiveBigIntegerField(blank=True, null=True, db_index=True)
    ficha_inscripcion_id = models.PositiveBigIntegerField(blank=True, null=True, db_index=True)
    estudiante_id = models.PositiveBigIntegerField(blank=True, null=True, db_index=True)
    forma_pago_id = models.PositiveBigIntegerField(blank=True, null=True, db_index=True)
    usuario_pago_id = models.PositiveBigIntegerField(blank=True, null=True, db_index=True)
    usuario_accion_id = models.PositiveBigIntegerField(blank=True, null=True, db_index=True)
    usuario_accion_username = models.CharField(max_length=150, blank=True)
    datos_anteriores = models.JSONField(default=dict, blank=True)
    datos_nuevos = models.JSONField(default=dict, blank=True)
    cambios = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    metodo_http = models.CharField(max_length=10, blank=True)
    ruta = models.TextField(blank=True)
    user_agent = models.TextField(blank=True)
    created = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = '"auditoria"."pago_auditoria"'
        ordering = ["-created", "-pk"]
        default_permissions = ("view",)
        indexes = (
            models.Index(fields=["pago_id", "-created"], name="audit_pago_fecha_idx"),
            models.Index(fields=["ficha_inscripcion_id", "-created"], name="audit_ficha_fecha_idx"),
            models.Index(fields=["usuario_accion_id", "-created"], name="audit_usuario_fecha_idx"),
        )

    def __str__(self):
        return f"{self.get_accion_display()} del pago #{self.pago_id}"

    def cambios_resumen(self):
        if self.accion == "crear":
            return "Registro inicial"
        return ", ".join(self.cambios) or "Sin cambios de valores"
