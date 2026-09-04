from django.urls import path

from . import views

app_name = "matricula"

urlpatterns = [
    path("matricular/", views.MatriculaProcesoView.as_view(), name="matricula_proceso"),
    path("representantes/<int:pk>/prefill/", views.representante_prefill, name="representante_prefill"),
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
    path("fichas/<int:pk>/documentos/", views.ficha_documentos, name="ficha_documentos"),
    path("fichas/<int:pk>/documentos/odt/", views.ficha_odt, name="ficha_odt"),
    path("fichas/<int:pk>/documentos/pdf/", views.ficha_pdf, name="ficha_pdf"),
    path("fichas/<int:pk>/documentos/contrato/docx/", views.contrato_docx, name="contrato_docx"),
    path("fichas/<int:pk>/documentos/contrato/pdf/", views.contrato_pdf, name="contrato_pdf"),
]
