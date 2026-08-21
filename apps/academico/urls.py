from django.urls import path

from . import views

app_name = "academico"

urlpatterns = [
    path("asignaturas/", views.AsignaturaListView.as_view(), name="asignatura_list"),
    path("asignaturas/nueva/", views.AsignaturaCreateView.as_view(), name="asignatura_nueva"),
    path("asignaturas/<int:pk>/editar/", views.AsignaturaUpdateView.as_view(), name="asignatura_editar"),
    path("temarios/", views.TemarioListView.as_view(), name="temario_list"),
    path("temarios/nuevo/", views.TemarioCreateView.as_view(), name="temario_nuevo"),
    path("temarios/<int:pk>/editar/", views.TemarioUpdateView.as_view(), name="temario_editar"),
    path("temas/", views.TemaListView.as_view(), name="tema_list"),
    path("temas/nuevo/", views.TemaCreateView.as_view(), name="tema_nuevo"),
    path("temas/<int:pk>/editar/", views.TemaUpdateView.as_view(), name="tema_editar"),
    path("planificaciones/", views.PlanificacionClaseListView.as_view(), name="planificacion_list"),
    path("planificaciones/nueva/", views.PlanificacionClaseCreateView.as_view(), name="planificacion_nueva"),
    path("planificaciones/<int:pk>/editar/", views.PlanificacionClaseUpdateView.as_view(), name="planificacion_editar"),
    path("bancos-preguntas/", views.BancoPreguntaListView.as_view(), name="banco_list"),
    path("bancos-preguntas/nuevo/", views.BancoPreguntaCreateView.as_view(), name="banco_nuevo"),
    path("bancos-preguntas/<int:pk>/editar/", views.BancoPreguntaUpdateView.as_view(), name="banco_editar"),
    path("preguntas/", views.PreguntaListView.as_view(), name="pregunta_list"),
    path("preguntas/nueva/", views.PreguntaCreateView.as_view(), name="pregunta_nueva"),
    path("preguntas/<int:pk>/editar/", views.PreguntaUpdateView.as_view(), name="pregunta_editar"),
]
