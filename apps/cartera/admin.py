from django.contrib import admin

from .models import Cuota, FormaPago, Pago, PlanPago


class CuotaInline(admin.TabularInline):
    model = Cuota
    extra = 0


@admin.register(FormaPago)
class FormaPagoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "tipo", "empresa", "orden", "es_venta", "es_pago", "activo")
    list_filter = ("empresa", "activo", "es_venta", "es_pago")
    search_fields = ("nombre", "tipo")


@admin.register(PlanPago)
class PlanPagoAdmin(admin.ModelAdmin):
    list_display = ("ficha_inscripcion", "valor_total", "descuento", "abono", "saldo", "estado", "activo")
    list_filter = ("empresa", "estado", "activo")
    search_fields = ("ficha_inscripcion__numero", "ficha_inscripcion__estudiante__nombre")
    inlines = [CuotaInline]


@admin.register(Cuota)
class CuotaAdmin(admin.ModelAdmin):
    list_display = (
        "plan_pago",
        "numero",
        "fecha_pago_debito",
        "valor",
        "valor_pagado",
        "estado",
        "prioridad",
    )
    list_filter = ("estado", "prioridad", "fecha_pago_debito", "activo")
    search_fields = ("plan_pago__ficha_inscripcion__numero", "plan_pago__ficha_inscripcion__estudiante__nombre")
    date_hierarchy = "fecha_pago_debito"


@admin.register(Pago)
class PagoAdmin(admin.ModelAdmin):
    list_display = ("cuota", "fecha_registro", "valor", "forma_pago", "numero_documento", "usuario")
    list_filter = ("empresa", "forma_pago", "fecha_registro")
    search_fields = ("numero_documento", "cuota__plan_pago__ficha_inscripcion__numero")
    date_hierarchy = "fecha_registro"
