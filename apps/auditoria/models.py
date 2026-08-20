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
