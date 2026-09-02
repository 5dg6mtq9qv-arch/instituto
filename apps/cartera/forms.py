from pathlib import Path

from django import forms
from django.utils import timezone
from django.utils.html import format_html
from django.db.models import Max
from django.utils.text import slugify

from apps.core.forms import BootstrapFormMixin

from .models import Cuota, FormaPago, Pago, PlanPago


def get_pago_file_owner_label(pago):
    try:
        estudiante = pago.cuota.plan_pago.ficha_inscripcion.estudiante
    except Exception:
        estudiante = None
    if estudiante and estudiante.nombre:
        return estudiante.nombre

    user = getattr(pago, "usuario", None) or getattr(pago, "usuario_updated", None)
    if not user:
        return "usuario"
    try:
        partner = user.partner
    except Exception:
        partner = None
    if partner and partner.nombre:
        return partner.nombre
    return user.get_full_name() or user.get_username()


def build_pago_comprobante_filename(pago, original_name):
    extension = Path(original_name or "").suffix.lower()
    fecha = pago.fecha_registro or timezone.now()
    if timezone.is_aware(fecha):
        fecha = timezone.localtime(fecha)
    usuario = slugify(get_pago_file_owner_label(pago)) or "usuario"
    cuota = f"cuota_{pago.cuota_id}" if pago.cuota_id else "cuota"
    return f"{usuario}_{fecha:%Y%m%d_%H%M}_{cuota}{extension}"


def prepare_pago_comprobante_file(uploaded_file, pago, original_name=None):
    if not uploaded_file or not hasattr(uploaded_file, "name") or not hasattr(uploaded_file, "chunks"):
        return uploaded_file
    uploaded_file.name = build_pago_comprobante_filename(pago, original_name or uploaded_file.name)
    return uploaded_file


def pago_comprobante_duplicado(numero_documento, empresa=None, exclude_pk=None):
    numero_documento = (numero_documento or "").strip()
    if not numero_documento:
        return None
    pagos = Pago.objects.select_related(
        "cuota__plan_pago__ficha_inscripcion__estudiante",
        "forma_pago",
    ).filter(numero_documento__iexact=numero_documento)
    if empresa:
        pagos = pagos.filter(empresa=empresa)
    if exclude_pk:
        pagos = pagos.exclude(pk=exclude_pk)
    return pagos.order_by("-fecha_registro", "-pk").first()


def pago_comprobante_duplicado_message(pago):
    try:
        estudiante = pago.cuota.plan_pago.ficha_inscripcion.estudiante
    except Exception:
        estudiante = None
    estudiante_nombre = getattr(estudiante, "nombre", None) or "otro estudiante"
    numero_documento = pago.numero_documento or f"#{pago.pk}"
    return f"Este comprobante ya está relacionado al pago {numero_documento} por {pago.valor:.2f} de {estudiante_nombre}."


class ComprobantePagoFileInput(forms.ClearableFileInput):
    def get_file_icon(self, file_name):
        extension = Path(file_name).suffix.lower()
        if extension == ".pdf":
            return "ri-file-pdf-2-line"
        if extension in {".xls", ".xlsx", ".csv"}:
            return "ri-file-excel-2-line"
        if extension in {".doc", ".docx"}:
            return "ri-file-word-2-line"
        if extension in {".jpg", ".jpeg", ".png", ".webp"}:
            return "ri-image-line"
        return "ri-attachment-2"

    def render(self, name, value, attrs=None, renderer=None):
        input_html = forms.FileInput.render(self, name, None, attrs=attrs, renderer=renderer)
        if not value:
            return input_html
        try:
            file_url = value.url
        except ValueError:
            return input_html

        file_name = Path(getattr(value, "name", "") or "").name
        icon = self.get_file_icon(file_name)
        clear_html = ""
        if not self.is_required:
            clear_html = format_html(
                '<label class="payment-file-clear" for="{}">'
                '<input type="checkbox" name="{}" id="{}"> Limpiar archivo'
                "</label>",
                self.clear_checkbox_id(name),
                self.clear_checkbox_name(name),
                self.clear_checkbox_id(name),
            )
        return format_html(
            '<div class="payment-file-widget">'
            '<a class="payment-file-link" href="{}" target="_blank" rel="noopener">'
            '<i class="{}"></i><span>{}</span><strong>Descargar</strong>'
            "</a>{}</div>"
            '<span class="payment-file-change-label">Modificar comprobante</span>{}',
            file_url,
            icon,
            file_name or value,
            clear_html,
            input_html,
        )


class RegistrarPagoCuotasForm(BootstrapFormMixin, forms.Form):
    cuotas = forms.ModelMultipleChoiceField(
        queryset=Cuota.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    valor = forms.DecimalField(
        label="Valor a abonar",
        required=False,
        min_value=0.01,
        max_digits=12,
        decimal_places=2,
        widget=forms.NumberInput(attrs={"step": "0.01", "min": "0.01", "placeholder": "0.00", "data-payment-amount": ""}),
    )
    forma_pago = forms.ModelChoiceField(queryset=FormaPago.objects.none(), label="Forma de pago")
    fecha_registro = forms.DateTimeField(
        label="Fecha registro",
        input_formats=["%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"],
        widget=forms.DateTimeInput(format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"}),
    )
    numero_documento = forms.CharField(label="No. comprobante / referencia", max_length=60, required=False)
    comprobante = forms.FileField(required=False)
    comentario = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, **kwargs):
        cuotas_queryset = kwargs.pop("cuotas_queryset", Cuota.objects.none())
        empresa = kwargs.pop("empresa", None)
        super().__init__(*args, **kwargs)
        self.empresa = empresa
        self.fields["cuotas"].queryset = cuotas_queryset
        self.fields["fecha_registro"].initial = timezone.localtime().strftime("%Y-%m-%dT%H:%M")
        formas_pago = FormaPago.objects.filter(activo=True, es_pago=True)
        if empresa:
            formas_pago = formas_pago.filter(empresa=empresa)
        self.fields["forma_pago"].queryset = formas_pago.order_by("orden", "nombre")

    def clean(self):
        cleaned_data = super().clean()
        numero_documento = (cleaned_data.get("numero_documento") or "").strip()
        cleaned_data["numero_documento"] = numero_documento
        pago_duplicado = pago_comprobante_duplicado(numero_documento, empresa=self.empresa)
        if pago_duplicado:
            self.add_error("numero_documento", pago_comprobante_duplicado_message(pago_duplicado))

        cuotas = cleaned_data.get("cuotas")
        valor = cleaned_data.get("valor")
        if not cuotas and not valor:
            raise forms.ValidationError("Selecciona cuotas o ingresa un valor a abonar.")

        target_cuotas = cuotas or self.fields["cuotas"].queryset
        target_saldo = sum((cuota.saldo() for cuota in target_cuotas), 0)
        if valor and target_saldo <= 0:
            self.add_error("valor", "No hay saldo pendiente para registrar este abono.")
        elif valor and valor > target_saldo:
            self.add_error("valor", f"El abono no puede superar el saldo disponible: {target_saldo:.2f}.")
        return cleaned_data


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
        plan.valor_matricula = plan.valor_matricula or 0
        plan.descuento = plan.descuento or 0
        plan.valor_total = (plan.abono or 0) + (plan.saldo or 0) + plan.descuento
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
            "fecha_registro": forms.DateTimeInput(format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"}),
            "comprobante": ComprobantePagoFileInput(),
            "comentario": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["fecha_registro"].input_formats = ["%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"]

    def clean(self):
        cleaned_data = super().clean()
        numero_documento = (cleaned_data.get("numero_documento") or "").strip()
        cleaned_data["numero_documento"] = numero_documento
        pago_duplicado = pago_comprobante_duplicado(
            numero_documento,
            empresa=cleaned_data.get("empresa"),
            exclude_pk=self.instance.pk,
        )
        if pago_duplicado:
            self.add_error("numero_documento", pago_comprobante_duplicado_message(pago_duplicado))
        return cleaned_data

    def save(self, commit=True):
        comprobante = self.cleaned_data.get("comprobante")
        prepare_pago_comprobante_file(comprobante, self.instance)
        return super().save(commit=commit)
