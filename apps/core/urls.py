from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("empresas/", views.EmpresaListView.as_view(), name="empresa_list"),
    path("empresas/nueva/", views.EmpresaCreateView.as_view(), name="empresa_nueva"),
    path("empresas/<int:pk>/editar/", views.EmpresaUpdateView.as_view(), name="empresa_editar"),
    path("estudiantes/", views.EstudianteListView.as_view(), name="estudiante_list"),
    path("estudiantes/<int:pk>/editar/", views.EstudianteUpdateView.as_view(), name="estudiante_editar"),
    path("representantes/", views.RepresentanteListView.as_view(), name="representante_list"),
    path("representantes/<int:pk>/editar/", views.RepresentanteUpdateView.as_view(), name="representante_editar"),
    path("docentes/", views.DocenteListView.as_view(), name="docente_list"),
    path("docentes/nuevo/", views.DocenteCreateView.as_view(), name="docente_nuevo"),
    path("docentes/<int:pk>/editar/", views.DocenteUpdateView.as_view(), name="docente_editar"),
    path("personas/", views.PartnerListView.as_view(), name="partner_list"),
    path("personas/nueva/", views.PartnerCreateView.as_view(), name="partner_nuevo"),
    path("personas/<int:pk>/editar/", views.PartnerUpdateView.as_view(), name="partner_editar"),
    path("mi-perfil/", views.MiPerfilView.as_view(), name="mi_perfil"),
    path("grupos/", views.GroupListView.as_view(), name="grupo_list"),
    path("grupos/nuevo/", views.GroupCreateView.as_view(), name="grupo_nuevo"),
    path("grupos/<int:pk>/editar/", views.GroupUpdateView.as_view(), name="grupo_editar"),
    path("usuarios/", views.SystemUserListView.as_view(), name="usuario_list"),
    path("usuarios/nuevo/", views.SystemUserCreateView.as_view(), name="usuario_nuevo"),
    path("usuarios/<int:pk>/editar/", views.SystemUserUpdateView.as_view(), name="usuario_editar"),
]
