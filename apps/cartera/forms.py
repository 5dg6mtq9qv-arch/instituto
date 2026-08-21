from django import forms

from apps.core.forms import BootstrapFormMixin

from .models import Cuota, FormaPago, Pago, PlanPago


class FormaPagoForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = FormaPago
        fields = ["empresa", "nombre", "tipo", "orden", "es_venta", "es_pago", "activo"]


class PlanPagoForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = PlanPago
        fields = [
            "empresa",
            "ficha_inscripcion",
            "valor_total",
            "valor_matricula",
            "descuento",
            "abono",
            "saldo",
            "estado",
            "observacion",
            "activo",
        ]
        widgets = {"observacion": forms.Textarea(attrs={"rows": 3})}


class CuotaForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Cuota
        fields = [
            "plan_pago",
            "numero",
            "fecha_pago_debito",
            "valor",
            "valor_pagado",
            "numero_recibo_factura_deposito",
            "observacion",
            "estado",
            "prioridad",
            "activo",
        ]
        widgets = {
            "fecha_pago_debito": forms.DateInput(attrs={"type": "date"}),
            "observacion": forms.Textarea(attrs={"rows": 3}),
        }


class PagoForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Pago
        fields = [
            "empresa",
            "cuota",
            "forma_pago",
            "fecha_registro",
            "valor",
            "numero_documento",
            "comprobante",
            "comentario",
        ]
        widgets = {
            "fecha_registro": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "comentario": forms.Textarea(attrs={"rows": 3}),
        }
