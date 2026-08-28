from django import forms
from django.db.models import Max
from django.utils.text import slugify

from apps.core.forms import BootstrapFormMixin

from .models import Cuota, FormaPago, Pago, PlanPago


class RegistrarPagoCuotasForm(BootstrapFormMixin, forms.Form):
    cuotas = forms.ModelMultipleChoiceField(queryset=Cuota.objects.none(), widget=forms.CheckboxSelectMultiple)
    forma_pago = forms.ModelChoiceField(queryset=FormaPago.objects.none(), label="Forma de pago")
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
        fields = ["empresa", "nombre", "activo"]
        labels = {
            "nombre": "Forma de pago",
        }
        widgets = {
            "activo": forms.CheckboxInput(attrs={"class": "js-switch"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        empresa = cleaned_data.get("empresa")
        nombre = cleaned_data.get("nombre")
        tipo = self.tipo_from_nombre(nombre)
        cleaned_data["tipo"] = tipo
        if empresa and tipo:
            exists = FormaPago.objects.filter(empresa=empresa, tipo=tipo).exclude(pk=self.instance.pk).exists()
            if exists:
                self.add_error("nombre", "Ya existe una forma de pago con este nombre.")
        return cleaned_data

    def save(self, commit=True):
        forma_pago = super().save(commit=False)
        forma_pago.tipo = self.cleaned_data["tipo"]
        forma_pago.es_venta = True
        forma_pago.es_pago = True
        if forma_pago.orden is None:
            last_order = (
                FormaPago.objects.filter(empresa=forma_pago.empresa).aggregate(Max("orden"))["orden__max"] or 0
            )
            forma_pago.orden = last_order + 1
        if commit:
            forma_pago.save()
            self.save_m2m()
        return forma_pago

    @staticmethod
    def tipo_from_nombre(nombre):
        return slugify(nombre or "").replace("-", "_")[:20]


class PlanPagoForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = PlanPago
        fields = [
            "empresa",
            "ficha_inscripcion",
            "abono",
            "saldo",
            "estado",
            "observacion",
            "activo",
        ]
        widgets = {"observacion": forms.Textarea(attrs={"rows": 3})}

    def save(self, commit=True):
        plan = super().save(commit=False)
        plan.valor_matricula = 0
        plan.descuento = 0
        plan.valor_total = (plan.abono or 0) + (plan.saldo or 0)
        if commit:
            plan.save()
            self.save_m2m()
        return plan


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
