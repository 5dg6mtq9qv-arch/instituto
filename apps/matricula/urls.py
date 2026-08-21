from django.urls import path

from . import views

app_name = "matricula"

urlpatterns = [
    path("periodos/", views.PeriodoAcademicoListView.as_view(), name="periodo_list"),
    path("periodos/nuevo/", views.PeriodoAcademicoCreateView.as_view(), name="periodo_nuevo"),
    path("periodos/<int:pk>/editar/", views.PeriodoAcademicoUpdateView.as_view(), name="periodo_editar"),
    path("cursos/", views.CursoListView.as_view(), name="curso_list"),
    path("cursos/nuevo/", views.CursoCreateView.as_view(), name="curso_nuevo"),
    path("cursos/<int:pk>/editar/", views.CursoUpdateView.as_view(), name="curso_editar"),
    path("aulas/", views.AulaListView.as_view(), name="aula_list"),
    path("aulas/nueva/", views.AulaCreateView.as_view(), name="aula_nueva"),
    path("aulas/<int:pk>/editar/", views.AulaUpdateView.as_view(), name="aula_editar"),
    path("fichas/", views.FichaInscripcionListView.as_view(), name="ficha_list"),
    path("fichas/nueva/", views.FichaInscripcionCreateView.as_view(), name="ficha_nueva"),
    path("fichas/<int:pk>/editar/", views.FichaInscripcionUpdateView.as_view(), name="ficha_editar"),
]
