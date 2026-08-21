from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("empresas/", views.EmpresaListView.as_view(), name="empresa_list"),
    path("empresas/nueva/", views.EmpresaCreateView.as_view(), name="empresa_nueva"),
    path("empresas/<int:pk>/editar/", views.EmpresaUpdateView.as_view(), name="empresa_editar"),
    path("personas/", views.PartnerListView.as_view(), name="partner_list"),
    path("personas/nueva/", views.PartnerCreateView.as_view(), name="partner_nuevo"),
    path("personas/<int:pk>/editar/", views.PartnerUpdateView.as_view(), name="partner_editar"),
]
