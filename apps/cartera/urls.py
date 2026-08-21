from django.urls import path

from . import views

app_name = "cartera"

urlpatterns = [
    path("formas-pago/", views.FormaPagoListView.as_view(), name="forma_pago_list"),
    path("formas-pago/nueva/", views.FormaPagoCreateView.as_view(), name="forma_pago_nueva"),
    path("formas-pago/<int:pk>/editar/", views.FormaPagoUpdateView.as_view(), name="forma_pago_editar"),
    path("planes/", views.PlanPagoListView.as_view(), name="plan_pago_list"),
    path("planes/nuevo/", views.PlanPagoCreateView.as_view(), name="plan_pago_nuevo"),
    path("planes/<int:pk>/editar/", views.PlanPagoUpdateView.as_view(), name="plan_pago_editar"),
    path("cuotas/", views.CuotaListView.as_view(), name="cuota_list"),
    path("cuotas/nueva/", views.CuotaCreateView.as_view(), name="cuota_nueva"),
    path("cuotas/<int:pk>/editar/", views.CuotaUpdateView.as_view(), name="cuota_editar"),
    path("pagos/", views.PagoListView.as_view(), name="pago_list"),
    path("pagos/nuevo/", views.PagoCreateView.as_view(), name="pago_nuevo"),
    path("pagos/<int:pk>/editar/", views.PagoUpdateView.as_view(), name="pago_editar"),
]
