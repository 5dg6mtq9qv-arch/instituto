from django.db.models import Q
from django.urls import reverse_lazy

from apps.core.forms import EmpresaForm, PartnerForm
from apps.core.web_views import InstitutoCreateView, InstitutoListView, InstitutoUpdateView

from .models import Empresa, Partner


class EmpresaListView(InstitutoListView):
    model = Empresa
    title = "Empresas"
    create_url_name = "core:empresa_nueva"
    columns = (
        ("Nombre comercial", "nombre_comercial"),
        ("RUC", "ruc"),
        ("Telefono", "telefono"),
        ("Ciudad", "ciudad"),
        ("Activa", "activa"),
    )


class EmpresaCreateView(InstitutoCreateView):
    model = Empresa
    form_class = EmpresaForm
    title = "Nueva empresa"
    success_url = reverse_lazy("core:empresa_list")
    cancel_url = reverse_lazy("core:empresa_list")


class EmpresaUpdateView(InstitutoUpdateView):
    model = Empresa
    form_class = EmpresaForm
    title = "Editar empresa"
    success_url = reverse_lazy("core:empresa_list")
    cancel_url = reverse_lazy("core:empresa_list")


class PartnerListView(InstitutoListView):
    model = Partner
    title = "Personas"
    create_url_name = "core:partner_nuevo"
    columns = (
        ("Nombre", "nombre"),
        ("Identificacion", "identificacion"),
        ("Telefono", "telefono_celular"),
        ("Email", "email"),
        ("Estudiante", "es_estudiante"),
        ("Representante", "es_representante"),
        ("Docente", "es_docente"),
    )

    def get_queryset(self):
        queryset = super().get_queryset().select_related("tipo_identificacion", "empresa")
        q = self.request.GET.get("q")
        if q:
            queryset = queryset.filter(
                Q(nombre__icontains=q)
                | Q(identificacion__icontains=q)
                | Q(telefono_celular__icontains=q)
                | Q(email__icontains=q)
            )
        return queryset


class PartnerCreateView(InstitutoCreateView):
    model = Partner
    form_class = PartnerForm
    title = "Nueva persona"
    success_url = reverse_lazy("core:partner_list")
    cancel_url = reverse_lazy("core:partner_list")


class PartnerUpdateView(InstitutoUpdateView):
    model = Partner
    form_class = PartnerForm
    title = "Editar persona"
    success_url = reverse_lazy("core:partner_list")
    cancel_url = reverse_lazy("core:partner_list")
