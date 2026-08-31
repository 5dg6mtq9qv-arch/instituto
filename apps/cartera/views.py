from decimal import Decimal

from django.db import transaction
from django.db.models import Prefetch, Q, Sum
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View

from apps.core.web_views import InstitutoCreateView, InstitutoListView, InstitutoUpdateView
from apps.matricula.models import FichaInscripcion

from .forms import (
    CuotaForm,
    FormaPagoForm,
    PagoForm,
    PlanPagoForm,
    RegistrarPagoCuotasForm,
    prepare_pago_comprobante_file,
)
from .models import Cuota, FormaPago, Pago, PlanPago


class AlumnoCarteraListView(InstitutoListView):
    model = FichaInscripcion
    title = "Cobros por alumno"
    template_name = "cartera/alumno_cartera_list.html"
    update_url_name = "cartera:alumno_pendientes"
    columns = (
        ("Alumno", "estudiante"),
        ("Ficha", "numero"),
        ("Aula", "aula"),
        ("Restante", "plan_pago.saldo"),
        ("Estado", "estado"),
    )
    STATUS_TABS = (
        ("todos", "Todos", "ri-team-line"),
        ("vencidos", "Vencidos", "ri-error-warning-line"),
        ("pendientes", "Pendientes", "ri-bill-line"),
        ("al-dia", "Al dia", "ri-shield-check-line"),
        ("cerrados", "Cerrados", "ri-checkbox-circle-line"),
    )

    def get_permission_required(self):
        return ("cartera.view_cuota",)

    def overdue_cuota_filter(self):
        today = timezone.localdate()
        return Q(plan_pago__cuotas__activo=True) & (
            Q(plan_pago__cuotas__estado="vencida")
            | Q(plan_pago__cuotas__estado__in=["pendiente", "parcial"], plan_pago__cuotas__fecha_pago_debito__lt=today)
        )

    def get_base_queryset(self):
        cuotas = Cuota.objects.filter(activo=True).order_by("fecha_pago_debito", "numero")
        return (
            FichaInscripcion.objects.select_related("estudiante", "cliente", "representante", "aula", "plan_pago")
            .prefetch_related(Prefetch("plan_pago__cuotas", queryset=cuotas))
            .filter(plan_pago__isnull=False, activo=True)
            .order_by("estudiante__nombre")
        )

    def apply_search(self, queryset):
        q = self.request.GET.get("q")
        if not q:
            return queryset
        return queryset.filter(
            Q(estudiante__nombre__icontains=q)
            | Q(estudiante__identificacion__icontains=q)
            | Q(numero__icontains=q)
            | Q(aula__nombre__icontains=q)
            | Q(cliente__nombre__icontains=q)
            | Q(representante__nombre__icontains=q)
        )

    def get_selected_estado(self):
        selected = self.request.GET.get("estado", "todos")
        allowed = {key for key, _, _ in self.STATUS_TABS}
        return selected if selected in allowed else "todos"

    def apply_status_filter(self, queryset):
        selected = self.get_selected_estado()
        overdue_filter = self.overdue_cuota_filter()
        if selected == "vencidos":
            return queryset.filter(overdue_filter).distinct()
        if selected == "pendientes":
            return queryset.filter(plan_pago__saldo__gt=0).distinct()
        if selected == "al-dia":
            return queryset.filter(plan_pago__saldo__gt=0).exclude(overdue_filter).distinct()
        if selected == "cerrados":
            return queryset.filter(Q(plan_pago__saldo__lte=0) | Q(plan_pago__estado="cerrado")).distinct()
        return queryset

    def get_queryset(self):
        return self.apply_status_filter(self.apply_search(self.get_base_queryset()))

    def get_action_label(self, obj):
        return "Cobrar"

    def can_update_object(self, obj):
        return self.request.user.has_perm("cartera.view_cuota")

    def get_update_url(self, obj):
        if not self.can_update_object(obj):
            return ""
        return reverse_lazy("cartera:alumno_pendientes", kwargs={"pk": obj.pk})

    def build_status_url(self, status_key):
        query_params = self.request.GET.copy()
        query_params.pop("page", None)
        if status_key == "todos":
            query_params.pop("estado", None)
        else:
            query_params["estado"] = status_key
        query = query_params.urlencode()
        base_url = reverse("cartera:alumno_cartera_list")
        return f"{base_url}?{query}" if query else base_url

    def get_status_counts(self, queryset):
        overdue_filter = self.overdue_cuota_filter()
        return {
            "todos": queryset.count(),
            "vencidos": queryset.filter(overdue_filter).distinct().count(),
            "pendientes": queryset.filter(plan_pago__saldo__gt=0).distinct().count(),
            "al-dia": queryset.filter(plan_pago__saldo__gt=0).exclude(overdue_filter).distinct().count(),
            "cerrados": queryset.filter(Q(plan_pago__saldo__lte=0) | Q(plan_pago__estado="cerrado")).distinct().count(),
        }

    def build_summary(self, queryset, counts):
        total_saldo = queryset.filter(plan_pago__saldo__gt=0).aggregate(total=Sum("plan_pago__saldo"))["total"]
        return {
            "total": counts["todos"],
            "vencidos": counts["vencidos"],
            "pendientes": counts["pendientes"],
            "al_dia": counts["al-dia"],
            "cerrados": counts["cerrados"],
            "saldo": total_saldo or Decimal("0"),
        }

    def get_cuota_state(self, cuota):
        is_pending = cuota.activo and cuota.estado in {"pendiente", "parcial", "vencida"} and cuota.saldo() > 0
        is_overdue = is_pending and (cuota.estado == "vencida" or cuota.fecha_pago_debito < timezone.localdate())
        return is_pending, is_overdue

    def build_student_cards(self, fichas):
        cards = []
        for ficha in fichas:
            cuotas = list(ficha.plan_pago.cuotas.all())
            pending_items = []
            overdue_items = []
            for cuota in cuotas:
                is_pending, is_overdue = self.get_cuota_state(cuota)
                if is_pending:
                    pending_items.append(cuota)
                if is_overdue:
                    overdue_items.append(cuota)
            next_cuota = pending_items[0] if pending_items else None
            overdue_balance = sum((cuota.saldo() for cuota in overdue_items), Decimal("0"))
            if ficha.plan_pago.saldo <= 0 or ficha.plan_pago.estado == "cerrado":
                status_key = "cerrado"
                status_label = "Cerrado"
            elif overdue_items:
                status_key = "vencido"
                status_label = "Vencido"
            else:
                status_key = "pendiente"
                status_label = "Pendiente"
            cards.append(
                {
                    "ficha": ficha,
                    "status_key": status_key,
                    "status_label": status_label,
                    "representante": ficha.representante or ficha.cliente,
                    "pending_count": len(pending_items),
                    "overdue_count": len(overdue_items),
                    "overdue_balance": overdue_balance,
                    "next_cuota": next_cuota,
                    "url": self.get_update_url(ficha),
                }
            )
        return cards

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        selected_estado = self.get_selected_estado()
        searched_queryset = self.apply_search(self.get_base_queryset())
        counts = self.get_status_counts(searched_queryset)
        context["selected_estado"] = selected_estado
        context["selected_estado_label"] = dict((key, label) for key, label, _ in self.STATUS_TABS)[selected_estado]
        context["student_payment_summary"] = self.build_summary(searched_queryset, counts)
        context["status_tabs"] = [
            {
                "key": key,
                "label": label,
                "icon": icon,
                "count": counts[key],
                "url": self.build_status_url(key),
                "is_active": key == selected_estado,
            }
            for key, label, icon in self.STATUS_TABS
        ]
        context["student_payment_cards"] = self.build_student_cards(context["object_list"])
        return context


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

    def get_context(self, ficha, cuotas, form):
        today = timezone.localdate()
        cuota_items = []
        total_pendiente = Decimal("0")
        total_vencido = Decimal("0")
        total_pagado_pendientes = Decimal("0")

        for cuota in cuotas:
            saldo = cuota.saldo()
            total_pendiente += saldo
            total_pagado_pendientes += cuota.valor_pagado
            is_overdue = cuota.estado == "vencida" or cuota.fecha_pago_debito < today
            if is_overdue:
                total_vencido += saldo
            if cuota.valor:
                progress = min(round((cuota.valor_pagado / cuota.valor) * 100), 100)
            else:
                progress = 0
            cuota_items.append(
                {
                    "cuota": cuota,
                    "saldo": saldo,
                    "is_overdue": is_overdue,
                    "days_overdue": max((today - cuota.fecha_pago_debito).days, 0),
                    "progress": progress,
                }
            )

        pagos_recientes = (
            Pago.objects.select_related("cuota", "forma_pago")
            .filter(cuota__plan_pago=ficha.plan_pago)
            .order_by("-fecha_registro")[:5]
        )

        return {
            "title": "Pagos pendientes",
            "ficha": ficha,
            "cuotas": cuotas,
            "cuota_items": cuota_items,
            "form": form,
            "today": today,
            "total_pendiente": total_pendiente,
            "total_vencido": total_vencido,
            "total_pagado_pendientes": total_pagado_pendientes,
            "cuotas_pendientes_count": len(cuota_items),
            "cuotas_vencidas_count": sum(1 for item in cuota_items if item["is_overdue"]),
            "proxima_cuota": cuota_items[0] if cuota_items else None,
            "pagos_recientes": pagos_recientes,
        }

    def get_payment_targets(self, cuotas, selected_cuotas):
        selected_ids = {cuota.pk for cuota in selected_cuotas}
        if selected_ids:
            cuotas = cuotas.filter(pk__in=selected_ids)
        return list(cuotas.order_by("fecha_pago_debito", "numero"))

    def apply_payment_to_cuotas(self, request, ficha, target_cuotas, form):
        valor_abono = form.cleaned_data.get("valor")
        uploaded_file = form.cleaned_data.get("comprobante")
        original_file_name = getattr(uploaded_file, "name", "")
        remaining = valor_abono
        total_pagado = Decimal("0")
        cuotas_afectadas = 0

        for cuota in target_cuotas:
            saldo = cuota.saldo()
            if saldo <= 0:
                continue
            valor_pago = saldo if remaining is None else min(saldo, remaining)
            if valor_pago <= 0:
                break
            pago = Pago(
                empresa=ficha.empresa,
                cuota=cuota,
                forma_pago=form.cleaned_data["forma_pago"],
                fecha_registro=form.cleaned_data["fecha_registro"],
                valor=valor_pago,
                numero_documento=form.cleaned_data.get("numero_documento"),
                comentario=form.cleaned_data.get("comentario"),
                usuario=request.user,
                usuario_updated=request.user,
            )
            if uploaded_file:
                if hasattr(uploaded_file, "seek"):
                    uploaded_file.seek(0)
                pago.comprobante = prepare_pago_comprobante_file(uploaded_file, pago, original_file_name)
            pago.save()
            cuota.valor_pagado += valor_pago
            cuota.estado = "pagada" if cuota.valor_pagado >= cuota.valor else "parcial"
            cuota.usuario_updated = request.user
            cuota.save(update_fields=["valor_pagado", "estado", "usuario_updated", "updated"])
            total_pagado += valor_pago
            cuotas_afectadas += 1

            if remaining is not None:
                remaining -= valor_pago
                if remaining <= 0:
                    break

        return total_pagado, cuotas_afectadas

    def get(self, request, pk):
        ficha = self.get_ficha(pk)
        cuotas = self.get_cuotas(ficha)
        form = RegistrarPagoCuotasForm(cuotas_queryset=cuotas, empresa=ficha.empresa)
        return render(request, self.template_name, self.get_context(ficha, cuotas, form))

    def post(self, request, pk):
        ficha = self.get_ficha(pk)
        cuotas = self.get_cuotas(ficha)
        form = RegistrarPagoCuotasForm(request.POST, request.FILES, cuotas_queryset=cuotas, empresa=ficha.empresa)
        if form.is_valid():
            selected_cuotas = form.cleaned_data["cuotas"]
            target_cuotas = self.get_payment_targets(cuotas, selected_cuotas)
            with transaction.atomic():
                total_pagado, cuotas_afectadas = self.apply_payment_to_cuotas(request, ficha, target_cuotas, form)
                if total_pagado <= 0:
                    form.add_error(None, "No se encontro saldo pendiente para registrar el pago.")
                    return render(request, self.template_name, self.get_context(ficha, cuotas, form))
                plan = ficha.plan_pago
                plan.abono += total_pagado
                plan.saldo = max(plan.valor_total - plan.descuento - plan.abono, Decimal("0"))
                if plan.saldo == 0:
                    plan.estado = "cerrado"
                plan.usuario_updated = request.user
                plan.save(update_fields=["abono", "saldo", "estado", "usuario_updated", "updated"])
            if form.cleaned_data.get("valor"):
                messages.success(request, f"Abono registrado por {total_pagado:.2f} en {cuotas_afectadas} cuota(s).")
            else:
                messages.success(request, f"Pago registrado por {total_pagado:.2f}.")
            return redirect("cartera:alumno_pendientes", pk=ficha.pk)
        return render(request, self.template_name, self.get_context(ficha, cuotas, form))


class FormaPagoListView(InstitutoListView):
    model = FormaPago
    title = "Formas de pago"
    create_url_name = "cartera:forma_pago_nueva"
    create_label = "Nueva forma"
    columns = (("Forma de pago", "nombre"), ("Activa", "activo"))


class FormaPagoCreateView(InstitutoCreateView):
    model = FormaPago
    form_class = FormaPagoForm
    template_name = "cartera/forma_pago_form.html"
    title = "Nueva forma de pago"
    success_url = reverse_lazy("cartera:forma_pago_list")
    cancel_url = reverse_lazy("cartera:forma_pago_list")


class FormaPagoUpdateView(InstitutoUpdateView):
    model = FormaPago
    form_class = FormaPagoForm
    template_name = "cartera/forma_pago_form.html"
    title = "Editar forma de pago"
    success_url = reverse_lazy("cartera:forma_pago_list")
    cancel_url = reverse_lazy("cartera:forma_pago_list")


class PlanPagoListView(InstitutoListView):
    model = PlanPago
    title = "Planes de pago"
    create_url_name = "cartera:plan_pago_nuevo"
    columns = (("Ficha", "ficha_inscripcion"), ("Abono", "abono"), ("Restante", "saldo"), ("Estado", "estado"))

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
    title = "Pagos registrados"
    create_url_name = None
    update_url_name = "cartera:pago_editar"
    columns = (("Fecha", "fecha_registro"), ("Cuota", "cuota"), ("Forma", "forma_pago"), ("Valor", "valor"), ("Documento", "numero_documento"))

    def get_queryset(self):
        return super().get_queryset().select_related("cuota", "forma_pago", "empresa")

    def get_action_label(self, obj):
        return "Ver pago"


class PagoCreateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "cartera.view_cuota"

    def get(self, request):
        messages.info(request, "Selecciona un alumno para registrar el pago desde su cartera.")
        return redirect("cartera:alumno_cartera_list")

    def post(self, request):
        return self.get(request)


class PagoUpdateView(InstitutoUpdateView):
    model = Pago
    form_class = PagoForm
    title = "Editar pago"
    success_url = reverse_lazy("cartera:pago_list")
    cancel_url = reverse_lazy("cartera:pago_list")
