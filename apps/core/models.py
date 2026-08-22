from django.contrib.postgres.fields import HStoreField
from django.db import models


class TipoIdentificacion(models.Model):
    nombre = models.CharField(max_length=30)
    codigo = models.CharField(max_length=10, blank=True, null=True)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = '"core"."tipo_identificacion"'
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Empresa(models.Model):
    ruc = models.CharField(max_length=13, default="", blank=True)
    razon_social = models.CharField(max_length=300, blank=True, null=True)
    nombre_comercial = models.CharField(max_length=300, blank=True, null=True)
    direccion = models.TextField(default="", blank=True)
    telefono = models.CharField(max_length=20, blank=True, null=True)
    email = models.TextField(blank=True, null=True)
    ciudad = models.CharField(max_length=80, blank=True, null=True)
    logo = models.TextField(blank=True, null=True)
    activa = models.BooleanField(default=True)
    tags = HStoreField(blank=True, null=True, default=dict)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    usuario_updated = models.ForeignKey(
        "auth.User",
        db_column="id_usuario_updated",
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
        related_name="empresas_actualizadas",
    )

    class Meta:
        db_table = '"core"."empresa"'
        ordering = ["razon_social"]

    def __str__(self):
        return self.nombre_comercial or self.razon_social or str(self.id)

    def nombre_display(self):
        return self.nombre_comercial or self.razon_social or ""


class OperadorMovil(models.Model):
    nombre = models.CharField(max_length=100)
    comentario = models.CharField(max_length=200, blank=True, null=True)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = '"core"."operador_movil"'
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Partner(models.Model):
    codigo = models.CharField(max_length=50, blank=True, null=True)
    codigo_aux = models.CharField(max_length=20, blank=True, null=True)
    nombre = models.TextField()
    tipo_identificacion = models.ForeignKey(
        TipoIdentificacion,
        db_column="id_tipo_identificacion",
        on_delete=models.DO_NOTHING,
    )
    identificacion = models.CharField(max_length=20, default="", unique=True)
    direccion = models.CharField(max_length=200, blank=True, null=True)
    telefono = models.CharField(max_length=50, blank=True, null=True)
    telefono_celular = models.CharField(max_length=50, blank=True, null=True)
    email = models.TextField(blank=True, null=True)
    fecha_nacimiento = models.DateField(blank=True, null=True)
    genero = models.CharField(max_length=1, blank=True, null=True)
    tipo = models.CharField(max_length=2, blank=True, null=True)
    ocupacion = models.CharField(max_length=100, blank=True, null=True)
    comentario = models.TextField(blank=True, null=True)
    empresa = models.ForeignKey(
        Empresa,
        db_column="id_empresa",
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
    )
    operador_movil = models.ForeignKey(
        OperadorMovil,
        db_column="id_operador_movil",
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
    )
    usuario = models.OneToOneField(
        "auth.User",
        db_column="id_usuario",
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
        related_name="partner",
    )
    es_cliente = models.BooleanField(default=True)
    es_estudiante = models.BooleanField(default=False)
    es_representante = models.BooleanField(default=False)
    es_docente = models.BooleanField(default=False)
    ingresar_portal = models.BooleanField(default=True)
    activo = models.BooleanField(default=True)
    tags = HStoreField(blank=True, null=True, default=dict)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)
    usuario_updated = models.ForeignKey(
        "auth.User",
        db_column="id_usuario_updated",
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
        related_name="partners_actualizados",
    )

    class Meta:
        db_table = '"core"."partner"'
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre

    def nombre_corto(self):
        return self.nombre


class PartnerPartner(models.Model):
    partner_a = models.ForeignKey(
        Partner,
        db_column="id_partner_a",
        on_delete=models.DO_NOTHING,
        related_name="relaciones_a",
    )
    partner_b = models.ForeignKey(
        Partner,
        db_column="id_partner_b",
        on_delete=models.DO_NOTHING,
        related_name="relaciones_b",
    )
    relacion = models.CharField(max_length=50)
    principal = models.BooleanField(default=False)
    contacto_emergencia = models.BooleanField(default=True)
    activo = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    usuario_updated = models.ForeignKey(
        "auth.User",
        db_column="id_usuario_updated",
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
        related_name="partner_relaciones_actualizadas",
    )

    class Meta:
        db_table = '"core"."partner_partner"'
        unique_together = (("partner_a", "partner_b", "relacion"),)

    def __str__(self):
        return f"{self.partner_a} - {self.partner_b}"
