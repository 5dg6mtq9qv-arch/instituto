from django.db.models import Q
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View

from apps.core.web_views import InstitutoCreateView, InstitutoListView, InstitutoUpdateView
from apps.matricula.models import FichaInscripcion

from .forms import CuotaForm, FormaPagoForm, PagoForm, PlanPagoForm, RegistrarPagoCuotasForm
from .models import Cuota, FormaPago, Pago, PlanPago


class AlumnoCarteraListView(InstitutoListView):
    model = FichaInscripcion
    title = "Alumnos cartera"
    update_url_name = "cartera:alumno_pendientes"
    columns = (
        ("Alumno", "estudiante"),
        ("Ficha", "numero"),
        ("Aula", "aula"),
        ("Saldo", "plan_pago.saldo"),
        ("Estado", "estado"),
    )

    def get_permission_required(self):
        return ("cartera.view_cuota",)

    def get_queryset(self):
        queryset = (
            FichaInscripcion.objects.select_related("estudiante", "aula", "plan_pago")
            .filter(plan_pago__isnull=False, activo=True)
            .order_by("estudiante__nombre")
        )
        q = self.request.GET.get("q")
        if q:
            queryset = queryset.filter(
                Q(estudiante__nombre__icontains=q)
                | Q(numero__icontains=q)
                | Q(aula__nombre__icontains=q)
                | Q(cliente__nombre__icontains=q)
            )
        return queryset

    def get_action_label(self, obj):
        return "Ver pendientes"

    def can_update_object(self, obj):
        return self.request.user.has_perm("cartera.view_cuota")

    def get_update_url(self, obj):
        if not self.can_update_object(obj):
            return ""
        return reverse_lazy("cartera:alumno_pendientes", kwargs={"pk": obj.pk})


class AlumnoCuotasPendientesView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "cartera.view_cuota"
    template_name = "cartera/alumno_pendientes.html"

    def get_ficha(self, pk):
        return get_object_or_404(
            FichaInscripcion.objects.select_related("estudiante", "aula", "plan_pago", "empresa"),
            pk=pk,
            plan_pago__isnull=False,
        )

    def get_cuotas(self, ficha):
        return ficha.plan_pago.cuotas.filter(activo=True, estado__in=["pendiente", "parcial", "vencida"]).order_by(
            "fecha_pago_debito", "numero"
        )

    def get(self, request, pk):
        ficha = self.get_ficha(pk)
        cuotas = self.get_cuotas(ficha)
        form = RegistrarPagoCuotasForm(cuotas_queryset=cuotas, empresa=ficha.empresa)
        return render(request, self.template_name, {"title": "Pagos pendientes", "ficha": ficha, "cuotas": cuotas, "form": form})

    def post(self, request, pk):
        ficha = self.get_ficha(pk)
        cuotas = self.get_cuotas(ficha)
        form = RegistrarPagoCuotasForm(request.POST, request.FILES, cuotas_queryset=cuotas, empresa=ficha.empresa)
        if form.is_valid():
            selected_cuotas = form.cleaned_data["cuotas"]
            total_pagado = 0
            for cuota in selected_cuotas:
                valor_pago = cuota.saldo()
                if valor_pago <= 0:
                    continue
                Pago.objects.create(
                    empresa=ficha.empresa,
                    cuota=cuota,
                    forma_pago=form.cleaned_data["forma_pago"],
                    fecha_registro=timezone.now(),
                    valor=valor_pago,
                    numero_documento=form.cleaned_data.get("numero_documento"),
                    comprobante=form.cleaned_data.get("comprobante"),
                    comentario=form.cleaned_data.get("comentario"),
                    usuario=request.user,
                    usuario_updated=request.user,
                )
                cuota.valor_pagado += valor_pago
                cuota.estado = "pagada" if cuota.valor_pagado >= cuota.valor else "parcial"
                cuota.usuario_updated = request.user
                cuota.save(update_fields=["valor_pagado", "estado", "usuario_updated", "updated"])
                total_pagado += valor_pago
            plan = ficha.plan_pago
            plan.abono += total_pagado
            plan.saldo = max(plan.valor_total - plan.descuento - plan.abono, 0)
            if plan.saldo == 0:
                plan.estado = "cerrado"
            plan.usuario_updated = request.user
            plan.save(update_fields=["abono", "saldo", "estado", "usuario_updated", "updated"])
            messages.success(request, f"Pago registrado por {total_pagado:.2f}.")
            return redirect("cartera:alumno_pendientes", pk=ficha.pk)
        return render(request, self.template_name, {"title": "Pagos pendientes", "ficha": ficha, "cuotas": cuotas, "form": form})


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
