from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Q
from django.urls import reverse
from django.utils.dateparse import parse_date
from django.views.generic import DetailView, ListView

from apps.cartera.models import Pago

from .models import PagoAuditoria


class AdministratorOnlyMixin(LoginRequiredMixin, UserPassesTestMixin):
    raise_exception = True

    def test_func(self):
        user = self.request.user
        return user.is_superuser or user.groups.filter(name="Administrador").exists()


class PagoAuditoriaListView(AdministratorOnlyMixin, ListView):
    model = PagoAuditoria
    template_name = "auditoria/pago_auditoria_list.html"
    context_object_name = "auditorias"
    paginate_by = 50

    def get_queryset(self):
        queryset = super().get_queryset()
        query = self.request.GET.get("q", "").strip()
        action = self.request.GET.get("accion", "").strip()
        date_from = parse_date(self.request.GET.get("desde", ""))
        date_to = parse_date(self.request.GET.get("hasta", ""))

        if query:
            matches = Q(usuario_accion_username__icontains=query)
            if query.isdigit():
                object_id = int(query)
                matches |= (
                    Q(pago_id=object_id)
                    | Q(empresa_id=object_id)
                    | Q(cuota_id=object_id)
                    | Q(plan_pago_id=object_id)
                    | Q(ficha_inscripcion_id=object_id)
                    | Q(estudiante_id=object_id)
                    | Q(forma_pago_id=object_id)
                    | Q(usuario_pago_id=object_id)
                    | Q(usuario_accion_id=object_id)
                )
            queryset = queryset.filter(matches)
        if action in dict(PagoAuditoria.ACCION_CHOICES):
            queryset = queryset.filter(accion=action)
        if date_from:
            queryset = queryset.filter(created__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(created__date__lte=date_to)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query_params = self.request.GET.copy()
        query_params.pop("page", None)
        context.update(
            {
                "title": "Auditoría de pagos",
                "action_choices": PagoAuditoria.ACCION_CHOICES,
                "pagination_query": query_params.urlencode(),
            }
        )
        return context


class PagoAuditoriaDetailView(AdministratorOnlyMixin, DetailView):
    model = PagoAuditoria
    template_name = "auditoria/pago_auditoria_detail.html"
    context_object_name = "auditoria"

    FIELD_LABELS = {
        "valor_cuota": "Valor de la cuota",
        "valor_total_plan": "Valor total del plan",
        "saldo_plan": "Saldo pendiente del plan",
        "valor_total_curso": "Valor total del curso",
        "saldo_ficha": "Saldo pendiente de la ficha",
        "empresa_id": "Empresa ID",
        "cuota_id": "Cuota ID",
        "forma_pago_id": "Forma de pago ID",
        "fecha_registro": "Fecha del pago",
        "valor": "Valor",
        "numero_documento": "Número de documento",
        "comprobante": "Comprobante",
        "comentario": "Comentario",
        "anulado": "Pago anulado",
        "fecha_anulacion": "Fecha de anulación",
        "motivo_anulacion": "Motivo de anulación",
        "usuario_id": "Usuario que registró el pago ID",
        "usuario_updated_id": "Último usuario del pago ID",
        "usuario_anulacion_id": "Usuario que anuló el pago ID",
        "cuota_valor_pagado": "Valor pagado de la cuota",
        "cuota_estado": "Estado de la cuota",
        "plan_abono": "Total abonado al plan",
        "plan_saldo": "Saldo pendiente del plan",
        "plan_estado": "Estado del plan",
        "ficha_abono": "Total abonado de la ficha",
        "ficha_saldo": "Saldo pendiente de la ficha",
    }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        audit = self.object
        if audit.accion == "crear":
            changes = [
                {
                    "field": field_name,
                    "label": self.FIELD_LABELS.get(field_name, field_name),
                    "before": None,
                    "after": value,
                }
                for field_name, value in audit.datos_nuevos.items()
            ]
        else:
            changes = [
                {
                    "field": field_name,
                    "label": self.FIELD_LABELS.get(field_name, field_name),
                    "before": values.get("antes"),
                    "after": values.get("despues"),
                }
                for field_name, values in audit.cambios.items()
            ]
        payment_exists = bool(audit.pago_id and Pago.objects.filter(pk=audit.pago_id).exists())
        object_label = f"pago #{audit.pago_id}" if audit.pago_id else f"cuota #{audit.cuota_id}"
        context.update(
            {
                "title": f"Auditoría de {object_label}",
                "changes": changes,
                "payment_url": reverse("cartera:pago_detalle", kwargs={"pk": audit.pago_id}) if payment_exists else "",
            }
        )
        return context
