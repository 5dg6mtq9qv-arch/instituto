from django.contrib.auth import get_user_model
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.auth.models import Group
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from apps.core.forms import (
    DocenteForm,
    EmpresaForm,
    EstudianteForm,
    GroupPermissionForm,
    MiPerfilPartnerForm,
    MiPerfilPasswordChangeForm,
    RepresentanteForm,
    SystemUserForm,
)
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


class PartnerListView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        return redirect("core:estudiante_list")


class PartnerTypeListView(InstitutoListView):
    model = Partner
    create_url_name = None
    update_url_name = None
    columns = (
        ("Nombre", "nombre"),
        ("Identificacion", "identificacion"),
        ("Celular", "telefono_celular"),
        ("Email", "email"),
        ("Estado", "estado_operativo"),
    )
    search_fields = ("nombre", "identificacion", "telefono", "telefono_celular", "email")

    def get_queryset(self):
        queryset = super().get_queryset().select_related("tipo_identificacion", "empresa")
        q = self.request.GET.get("q")
        if q:
            query = Q()
            for field in self.search_fields:
                query |= Q(**{f"{field}__icontains": q})
            queryset = queryset.filter(query)
        return queryset

    def get_column_value(self, obj, attr):
        if attr == "estado_operativo":
            return "Activo" if obj.activo else "Inactivo"
        if attr == "usuario_acceso":
            return obj.usuario.username if obj.usuario_id else "-"
        if attr == "representante_principal":
            return self.get_representante_principal(obj)
        if attr == "estudiantes_vinculados":
            return self.get_estudiantes_vinculados(obj)
        return super().get_column_value(obj, attr)

    def get_column_kind(self, attr):
        if attr == "estado_operativo":
            return "status"
        return super().get_column_kind(attr)

    def get_representante_principal(self, obj):
        representantes = [
            relacion.partner_b.nombre
            for relacion in obj.relaciones_a.all()
            if relacion.activo and relacion.relacion == "representante" and relacion.partner_b.es_representante
        ]
        return ", ".join(representantes) or "-"

    def get_estudiantes_vinculados(self, obj):
        estudiantes = [
            relacion.partner_a.nombre
            for relacion in obj.relaciones_b.all()
            if relacion.activo and relacion.relacion == "representante" and relacion.partner_a.es_estudiante
        ]
        return ", ".join(estudiantes) or "-"


class EstudianteListView(PartnerTypeListView):
    title = "Estudiantes"
    update_url_name = "core:estudiante_editar"
    columns = (
        ("Nombre", "nombre"),
        ("Identificacion", "identificacion"),
        ("Celular", "telefono_celular"),
        ("Email", "email"),
        ("Representante", "representante_principal"),
        ("Estado", "estado_operativo"),
    )

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(es_estudiante=True)
            .prefetch_related("relaciones_a__partner_b")
        )


class RepresentanteListView(PartnerTypeListView):
    title = "Representantes"
    update_url_name = "core:representante_editar"
    columns = (
        ("Nombre", "nombre"),
        ("Identificacion", "identificacion"),
        ("Celular", "telefono_celular"),
        ("Email", "email"),
        ("Estudiantes", "estudiantes_vinculados"),
        ("Estado", "estado_operativo"),
    )

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(es_representante=True)
            .prefetch_related("relaciones_b__partner_a")
        )


class PartnerCreateView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        raise PermissionDenied("Los estudiantes y representantes se crean desde el proceso de matricula.")

    def post(self, request, *args, **kwargs):
        raise PermissionDenied("Los estudiantes y representantes se crean desde el proceso de matricula.")


class PartnerUpdateView(LoginRequiredMixin, View):
    def get(self, request, pk, *args, **kwargs):
        return self.redirect_to_typed_view(request, pk)

    def post(self, request, pk, *args, **kwargs):
        return self.redirect_to_typed_view(request, pk)

    def redirect_to_typed_view(self, request, pk):
        partner = get_partner_for_legacy_redirect(pk)
        if partner.es_estudiante:
            return redirect("core:estudiante_editar", pk=partner.pk)
        if partner.es_representante:
            return redirect("core:representante_editar", pk=partner.pk)
        if partner.es_docente and user_can_manage_docentes(request.user):
            return redirect("core:docente_editar", pk=partner.pk)
        raise PermissionDenied("No hay una vista de edicion disponible para este registro.")


class EstudianteUpdateView(InstitutoUpdateView):
    model = Partner
    form_class = EstudianteForm
    title = "Editar estudiante"
    success_url = reverse_lazy("core:estudiante_list")
    cancel_url = reverse_lazy("core:estudiante_list")

    def get_queryset(self):
        return super().get_queryset().filter(es_estudiante=True)


class RepresentanteUpdateView(InstitutoUpdateView):
    model = Partner
    form_class = RepresentanteForm
    title = "Editar representante"
    success_url = reverse_lazy("core:representante_list")
    cancel_url = reverse_lazy("core:representante_list")

    def get_queryset(self):
        return super().get_queryset().filter(es_representante=True)


def user_can_manage_docentes(user):
    return user.is_authenticated and (user.is_superuser or user.groups.filter(name="Director").exists())


def get_partner_for_legacy_redirect(pk):
    return get_object_or_404(Partner, pk=pk)


class DocenteManagementMixin(UserPassesTestMixin):
    def test_func(self):
        return user_can_manage_docentes(self.request.user)

    def get_permission_required(self):
        return ()


class DocenteListView(DocenteManagementMixin, PartnerTypeListView):
    title = "Docentes"
    create_url_name = "core:docente_nuevo"
    create_label = "Nuevo docente"
    update_url_name = "core:docente_editar"
    columns = (
        ("Nombre", "nombre"),
        ("Identificacion", "identificacion"),
        ("Celular", "telefono_celular"),
        ("Email", "email"),
        ("Usuario", "usuario_acceso"),
        ("Estado", "estado_operativo"),
    )

    def get_queryset(self):
        return super().get_queryset().filter(es_docente=True).select_related("usuario")

    def can_create_object(self):
        return user_can_manage_docentes(self.request.user)

    def can_update_object(self, obj):
        return user_can_manage_docentes(self.request.user)


class DocenteCreateView(DocenteManagementMixin, InstitutoCreateView):
    model = Partner
    form_class = DocenteForm
    template_name = "core/docente_form.html"
    title = "Nuevo docente"
    success_url = reverse_lazy("core:docente_list")
    cancel_url = reverse_lazy("core:docente_list")


class DocenteUpdateView(DocenteManagementMixin, InstitutoUpdateView):
    model = Partner
    form_class = DocenteForm
    template_name = "core/docente_form.html"
    title = "Editar docente"
    success_url = reverse_lazy("core:docente_list")
    cancel_url = reverse_lazy("core:docente_list")

    def get_queryset(self):
        return super().get_queryset().filter(es_docente=True)


class MiPerfilView(LoginRequiredMixin, View):
    template_name = "core/mi_perfil.html"

    def get(self, request):
        return render(request, self.template_name, self.get_context())

    def post(self, request):
        if request.POST.get("form_type") == "password":
            password_form = MiPerfilPasswordChangeForm(request.user, request.POST)
            if password_form.is_valid():
                password_form.save()
                update_session_auth_hash(request, request.user)
                messages.success(request, "Contraseña actualizada correctamente.")
                return redirect("core:mi_perfil")
            return render(request, self.template_name, self.get_context(password_form=password_form))

        partner = self.get_partner()
        if partner is None:
            messages.warning(request, "Tu usuario no tiene un perfil vinculado.")
            return redirect("core:mi_perfil")

        form = MiPerfilPartnerForm(request.POST, request.FILES, instance=partner)
        if form.is_valid():
            perfil = form.save(commit=False)
            perfil.usuario_updated = request.user
            perfil.save()
            messages.success(request, "Perfil actualizado correctamente.")
            return redirect("core:mi_perfil")
        return render(request, self.template_name, self.get_context(form=form))

    def get_context(self, form=None, password_form=None):
        partner = self.get_partner()
        return {
            "title": "Mi perfil",
            "form": form if form is not None else (MiPerfilPartnerForm(instance=partner) if partner else None),
            "has_partner_profile": partner is not None,
            "is_docente_profile": bool(partner and partner.es_docente),
            "password_form": password_form if password_form is not None else MiPerfilPasswordChangeForm(self.request.user),
        }

    def get_partner(self):
        return getattr(self.request.user, "partner", None)


def user_is_system_admin(user):
    return user.is_authenticated and (
        user.is_superuser or user.groups.filter(name="Administrador").exists()
    )


class SecurityAccessMixin(UserPassesTestMixin):
    security_active_tab = ""

    def test_func(self):
        return user_is_system_admin(self.request.user)

    def get_permission_required(self):
        return ()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["security_active_tab"] = self.security_active_tab
        return context


class GroupListView(SecurityAccessMixin, InstitutoListView):
    model = Group
    security_active_tab = "groups"
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

    def can_create_object(self):
        return user_is_system_admin(self.request.user)

    def can_update_object(self, obj):
        return user_is_system_admin(self.request.user)


class GroupCreateView(SecurityAccessMixin, InstitutoCreateView):
    model = Group
    form_class = GroupPermissionForm
    security_active_tab = "groups"
    template_name = "core/group_form.html"
    title = "Nuevo grupo"
    success_url = reverse_lazy("core:grupo_list")
    cancel_url = reverse_lazy("core:grupo_list")


class GroupUpdateView(SecurityAccessMixin, InstitutoUpdateView):
    model = Group
    form_class = GroupPermissionForm
    security_active_tab = "groups"
    template_name = "core/group_form.html"
    title = "Editar grupo"
    success_url = reverse_lazy("core:grupo_list")
    cancel_url = reverse_lazy("core:grupo_list")


class SystemUserListView(SecurityAccessMixin, InstitutoListView):
    model = get_user_model()
    security_active_tab = "users"
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

    def can_create_object(self):
        return user_is_system_admin(self.request.user)

    def can_update_object(self, obj):
        return user_is_system_admin(self.request.user)


class SystemUserCreateView(SecurityAccessMixin, InstitutoCreateView):
    model = get_user_model()
    form_class = SystemUserForm
    security_active_tab = "users"
    template_name = "core/system_user_form.html"
    title = "Nuevo usuario del sistema"
    success_url = reverse_lazy("core:usuario_list")
    cancel_url = reverse_lazy("core:usuario_list")


class SystemUserUpdateView(SecurityAccessMixin, InstitutoUpdateView):
    model = get_user_model()
    form_class = SystemUserForm
    security_active_tab = "users"
    template_name = "core/system_user_form.html"
    title = "Editar usuario del sistema"
    success_url = reverse_lazy("core:usuario_list")
    cancel_url = reverse_lazy("core:usuario_list")
