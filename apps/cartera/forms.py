from django import forms

from apps.core.forms import BootstrapFormMixin

from .models import Cuota, FormaPago, Pago, PlanPago


class RegistrarPagoCuotasForm(BootstrapFormMixin, forms.Form):
    cuotas = forms.ModelMultipleChoiceField(queryset=Cuota.objects.none(), widget=forms.CheckboxSelectMultiple)
    forma_pago = forms.ModelChoiceField(queryset=FormaPago.objects.none(), label="Tipo de pago")
    numero_documento = forms.CharField(label="No. comprobante / referencia", max_length=60, required=False)
    comprobante = forms.FileField(required=False)
    comentario = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, **kwargs):
        cuotas_queryset = kwargs.pop("cuotas_queryset", Cuota.objects.none())
        empresa = kwargs.pop("empresa", None)
        super().__init__(*args, **kwargs)
        self.fields["cuotas"].queryset = cuotas_queryset
        formas_pago = FormaPago.objects.filter(activo=True, es_pago=True)
        if empresa:
            formas_pago = formas_pago.filter(empresa=empresa)
        self.fields["forma_pago"].queryset = formas_pago.order_by("orden", "nombre")


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
