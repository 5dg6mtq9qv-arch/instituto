from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.auth.models import Group
from django.db.models import Q
from django.urls import reverse_lazy

from apps.core.forms import EmpresaForm, GroupPermissionForm, PartnerForm, SystemUserForm
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


class SecurityAccessMixin(UserPassesTestMixin):
    def test_func(self):
        user = self.request.user
        return user.is_superuser or user.has_perm("auth.view_group") or user.has_perm("auth.change_group")


class SuperuserRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_superuser


class GroupListView(SecurityAccessMixin, InstitutoListView):
    model = Group
    title = "Grupos y permisos"
    create_url_name = "core:grupo_nuevo"
    update_url_name = "core:grupo_editar"
    columns = (
        ("Grupo", "name"),
        ("Usuarios", "usuarios_count"),
        ("Permisos", "permisos_count"),
    )

    def get_queryset(self):
        queryset = super().get_queryset().prefetch_related("permissions", "user_set").order_by("name")
        q = self.request.GET.get("q")
        if q:
            queryset = queryset.filter(name__icontains=q)
        return queryset

    def get_column_value(self, obj, attr):
        if attr == "usuarios_count":
            return obj.user_set.count()
        if attr == "permisos_count":
            return obj.permissions.count()
        return super().get_column_value(obj, attr)


class GroupCreateView(SecurityAccessMixin, InstitutoCreateView):
    model = Group
    form_class = GroupPermissionForm
    template_name = "core/group_form.html"
    title = "Nuevo grupo"
    success_url = reverse_lazy("core:grupo_list")
    cancel_url = reverse_lazy("core:grupo_list")

    def test_func(self):
        user = self.request.user
        return user.is_superuser or user.has_perm("auth.add_group")


class GroupUpdateView(SecurityAccessMixin, InstitutoUpdateView):
    model = Group
    form_class = GroupPermissionForm
    template_name = "core/group_form.html"
    title = "Editar grupo"
    success_url = reverse_lazy("core:grupo_list")
    cancel_url = reverse_lazy("core:grupo_list")

    def test_func(self):
        user = self.request.user
        return user.is_superuser or user.has_perm("auth.change_group")


class SystemUserListView(SuperuserRequiredMixin, InstitutoListView):
    model = get_user_model()
    title = "Usuarios del sistema"
    create_url_name = "core:usuario_nuevo"
    update_url_name = "core:usuario_editar"
    columns = (
        ("Usuario", "username"),
        ("Nombre", "get_full_name"),
        ("Correo", "email"),
        ("Activo", "is_active"),
        ("Admin Django", "is_staff"),
        ("Grupos", "group_names"),
    )

    def get_queryset(self):
        queryset = super().get_queryset().prefetch_related("groups").order_by("username")
        q = self.request.GET.get("q")
        if q:
            queryset = queryset.filter(
                Q(username__icontains=q)
                | Q(first_name__icontains=q)
                | Q(last_name__icontains=q)
                | Q(email__icontains=q)
                | Q(groups__name__icontains=q)
            ).distinct()
        return queryset

    def get_column_value(self, obj, attr):
        if attr == "group_names":
            return ", ".join(obj.groups.values_list("name", flat=True)) or "-"
        return super().get_column_value(obj, attr)


class SystemUserCreateView(SuperuserRequiredMixin, InstitutoCreateView):
    model = get_user_model()
    form_class = SystemUserForm
    template_name = "core/system_user_form.html"
    title = "Nuevo usuario del sistema"
    success_url = reverse_lazy("core:usuario_list")
    cancel_url = reverse_lazy("core:usuario_list")


class SystemUserUpdateView(SuperuserRequiredMixin, InstitutoUpdateView):
    model = get_user_model()
    form_class = SystemUserForm
    template_name = "core/system_user_form.html"
    title = "Editar usuario del sistema"
    success_url = reverse_lazy("core:usuario_list")
    cancel_url = reverse_lazy("core:usuario_list")
