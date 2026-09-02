from django.contrib import admin

from .forms import FormaPagoForm, PagoForm
from .models import Cuota, FormaPago, Pago, PlanPago


class CuotaInline(admin.TabularInline):
    model = Cuota
    extra = 0


@admin.register(FormaPago)
class FormaPagoAdmin(admin.ModelAdmin):
    form = FormaPagoForm
    list_display = ("nombre", "empresa", "activo")
    list_filter = ("empresa", "activo")
    search_fields = ("nombre",)


@admin.register(PlanPago)
class PlanPagoAdmin(admin.ModelAdmin):
    exclude = ("valor_total", "valor_matricula", "descuento")
    list_display = ("ficha_inscripcion", "abono", "restante", "estado", "activo")
    list_filter = ("empresa", "estado", "activo")
    search_fields = ("ficha_inscripcion__numero", "ficha_inscripcion__estudiante__nombre")
    inlines = [CuotaInline]

    def save_model(self, request, obj, form, change):
        obj.valor_matricula = 0
        obj.descuento = 0
        obj.valor_total = (obj.abono or 0) + (obj.saldo or 0)
        super().save_model(request, obj, form, change)

    @admin.display(description="Restante")
    def restante(self, obj):
        return obj.saldo


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
    form = PagoForm
    list_display = ("cuota", "fecha_registro", "valor", "forma_pago", "numero_documento", "usuario")
    list_filter = ("empresa", "forma_pago", "fecha_registro")
    search_fields = ("numero_documento", "cuota__plan_pago__ficha_inscripcion__numero")
    date_hierarchy = "fecha_registro"
