from django.contrib import admin

from .models import Empresa, OperadorMovil, Partner, PartnerPartner, TipoIdentificacion


@admin.register(TipoIdentificacion)
class TipoIdentificacionAdmin(admin.ModelAdmin):
    list_display = ("nombre", "codigo", "activo")
    list_filter = ("activo",)
    search_fields = ("nombre", "codigo")


@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ("ruc", "razon_social", "nombre_comercial", "ciudad", "activa")
    list_filter = ("activa", "ciudad")
    search_fields = ("ruc", "razon_social", "nombre_comercial")


@admin.register(OperadorMovil)
class OperadorMovilAdmin(admin.ModelAdmin):
    list_display = ("nombre", "activo")
    list_filter = ("activo",)
    search_fields = ("nombre",)


@admin.register(Partner)
class PartnerAdmin(admin.ModelAdmin):
    list_display = (
        "identificacion",
        "nombre",
        "empresa",
        "telefono_celular",
        "es_estudiante",
        "es_representante",
        "es_docente",
        "activo",
    )
    list_filter = ("empresa", "es_estudiante", "es_representante", "es_docente", "activo")
    search_fields = ("identificacion", "nombre", "telefono", "telefono_celular", "email")


@admin.register(PartnerPartner)
class PartnerPartnerAdmin(admin.ModelAdmin):
    list_display = ("partner_a", "partner_b", "relacion", "principal", "contacto_emergencia", "activo")
    list_filter = ("relacion", "principal", "contacto_emergencia", "activo")
    search_fields = ("partner_a__nombre", "partner_b__nombre", "relacion")
