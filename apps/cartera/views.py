from django.db.models import Q
from django.urls import reverse_lazy
from django.utils import timezone

from apps.core.web_views import InstitutoCreateView, InstitutoListView, InstitutoUpdateView

from .forms import CuotaForm, FormaPagoForm, PagoForm, PlanPagoForm
from .models import Cuota, FormaPago, Pago, PlanPago


class FormaPagoListView(InstitutoListView):
    model = FormaPago
    title = "Formas de pago"
    create_url_name = "cartera:forma_pago_nueva"
    columns = (("Nombre", "nombre"), ("Tipo", "tipo"), ("Orden", "orden"), ("Activa", "activo"))


class FormaPagoCreateView(InstitutoCreateView):
    model = FormaPago
    form_class = FormaPagoForm
    title = "Nueva forma de pago"
    success_url = reverse_lazy("cartera:forma_pago_list")
    cancel_url = reverse_lazy("cartera:forma_pago_list")


class FormaPagoUpdateView(InstitutoUpdateView):
    model = FormaPago
    form_class = FormaPagoForm
    title = "Editar forma de pago"
    success_url = reverse_lazy("cartera:forma_pago_list")
    cancel_url = reverse_lazy("cartera:forma_pago_list")


class PlanPagoListView(InstitutoListView):
    model = PlanPago
    title = "Planes de pago"
    create_url_name = "cartera:plan_pago_nuevo"
    columns = (("Ficha", "ficha_inscripcion"), ("Total", "valor_total"), ("Abono", "abono"), ("Saldo", "saldo"), ("Estado", "estado"))

    def get_queryset(self):
        return super().get_queryset().select_related("ficha_inscripcion", "empresa")


class PlanPagoCreateView(InstitutoCreateView):
    model = PlanPago
    form_class = PlanPagoForm
    title = "Nuevo plan de pago"
    success_url = reverse_lazy("cartera:plan_pago_list")
    cancel_url = reverse_lazy("cartera:plan_pago_list")


class PlanPagoUpdateView(InstitutoUpdateView):
    model = PlanPago
    form_class = PlanPagoForm
    title = "Editar plan de pago"
    success_url = reverse_lazy("cartera:plan_pago_list")
    cancel_url = reverse_lazy("cartera:plan_pago_list")


class CuotaListView(InstitutoListView):
    model = Cuota
    title = "Cuotas"
    create_url_name = "cartera:cuota_nueva"
    columns = (("Plan", "plan_pago"), ("No.", "numero"), ("Fecha", "fecha_pago_debito"), ("Valor", "valor"), ("Pagado", "valor_pagado"), ("Estado", "estado"))

    def get_queryset(self):
        queryset = super().get_queryset().select_related("plan_pago", "plan_pago__ficha_inscripcion")
        q = self.request.GET.get("q")
        if q:
            queryset = queryset.filter(
                Q(plan_pago__ficha_inscripcion__numero__icontains=q)
                | Q(plan_pago__ficha_inscripcion__estudiante__nombre__icontains=q)
                | Q(numero_recibo_factura_deposito__icontains=q)
            )
        return queryset


class CuotaCreateView(InstitutoCreateView):
    model = Cuota
    form_class = CuotaForm
    title = "Nueva cuota"
    success_url = reverse_lazy("cartera:cuota_list")
    cancel_url = reverse_lazy("cartera:cuota_list")


class CuotaUpdateView(InstitutoUpdateView):
    model = Cuota
    form_class = CuotaForm
    title = "Editar cuota"
    success_url = reverse_lazy("cartera:cuota_list")
    cancel_url = reverse_lazy("cartera:cuota_list")


class PagoListView(InstitutoListView):
    model = Pago
    title = "Pagos"
    create_url_name = "cartera:pago_nuevo"
    columns = (("Fecha", "fecha_registro"), ("Cuota", "cuota"), ("Forma", "forma_pago"), ("Valor", "valor"), ("Documento", "numero_documento"))

    def get_queryset(self):
        return super().get_queryset().select_related("cuota", "forma_pago", "empresa")


class PagoCreateView(InstitutoCreateView):
    model = Pago
    form_class = PagoForm
    title = "Registrar pago"
    success_url = reverse_lazy("cartera:pago_list")
    cancel_url = reverse_lazy("cartera:pago_list")

    def get_initial(self):
        initial = super().get_initial()
        initial.setdefault("fecha_registro", timezone.localtime().strftime("%Y-%m-%dT%H:%M"))
        return initial

    def form_valid(self, form):
        if hasattr(form.instance, "usuario"):
            form.instance.usuario = self.request.user
        return super().form_valid(form)


class PagoUpdateView(InstitutoUpdateView):
    model = Pago
    form_class = PagoForm
    title = "Editar pago"
    success_url = reverse_lazy("cartera:pago_list")
    cancel_url = reverse_lazy("cartera:pago_list")
