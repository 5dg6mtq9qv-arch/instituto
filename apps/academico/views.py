from django.urls import reverse_lazy
from django.db.models import Q

from apps.core.web_views import InstitutoCreateView, InstitutoListView, InstitutoUpdateView

from .forms import (
    AsignaturaForm,
    BancoPreguntaForm,
    HorarioClaseForm,
    PlanificacionClaseForm,
    PreguntaForm,
    TemaForm,
    TemarioForm,
)
from .models import Asignatura, BancoPregunta, HorarioClase, PlanificacionClase, Pregunta, Tema, Temario


class AsignaturaListView(InstitutoListView):
    model = Asignatura
    title = "Asignaturas"
    create_url_name = "academico:asignatura_nueva"
    columns = (("Codigo", "codigo"), ("Nombre", "nombre"), ("Activo", "activo"))


class AsignaturaCreateView(InstitutoCreateView):
    model = Asignatura
    form_class = AsignaturaForm
    title = "Nueva asignatura"
    success_url = reverse_lazy("academico:asignatura_list")
    cancel_url = reverse_lazy("academico:asignatura_list")


class AsignaturaUpdateView(InstitutoUpdateView):
    model = Asignatura
    form_class = AsignaturaForm
    title = "Editar asignatura"
    success_url = reverse_lazy("academico:asignatura_list")
    cancel_url = reverse_lazy("academico:asignatura_list")


class TemarioListView(InstitutoListView):
    model = Temario
    title = "Temarios"
    create_url_name = "academico:temario_nuevo"
    columns = (("Asignatura", "asignatura"), ("Nombre", "nombre"), ("Periodo", "periodo_academico"), ("Estado", "estado"))

    def get_queryset(self):
        return super().get_queryset().select_related("asignatura", "periodo_academico", "empresa")


class TemarioCreateView(InstitutoCreateView):
    model = Temario
    form_class = TemarioForm
    title = "Nuevo temario"
    success_url = reverse_lazy("academico:temario_list")
    cancel_url = reverse_lazy("academico:temario_list")


class TemarioUpdateView(InstitutoUpdateView):
    model = Temario
    form_class = TemarioForm
    title = "Editar temario"
    success_url = reverse_lazy("academico:temario_list")
    cancel_url = reverse_lazy("academico:temario_list")


class HorarioClaseListView(InstitutoListView):
    model = HorarioClase
    title = "Horarios de clase"
    create_url_name = "academico:horario_nuevo"
    columns = (
        ("Fecha", "fecha"),
        ("Hora", "rango_hora"),
        ("Aula", "aula"),
        ("Asignatura", "asignatura"),
        ("Docente", "docente"),
        ("Tutor", "tutor"),
        ("Periodo", "periodo_academico"),
        ("Estado", "estado"),
    )

    def get_queryset(self):
        queryset = (
            super()
            .get_queryset()
            .select_related("empresa", "periodo_academico", "aula", "asignatura", "docente", "tutor")
        )
        q = self.request.GET.get("q")
        if q:
            queryset = queryset.filter(
                Q(aula__nombre__icontains=q)
                | Q(asignatura__nombre__icontains=q)
                | Q(docente__nombre__icontains=q)
                | Q(tutor__nombre__icontains=q)
                | Q(periodo_academico__nombre__icontains=q)
                | Q(tipo_planificacion__icontains=q)
                | Q(tema_previsto__icontains=q)
                | Q(observacion__icontains=q)
            )
        return queryset

    def get_column_value(self, obj, attr):
        if attr == "rango_hora":
            return f"{obj.hora_inicio:%H:%M} - {obj.hora_fin:%H:%M}"
        return super().get_column_value(obj, attr)


class HorarioClaseCreateView(InstitutoCreateView):
    model = HorarioClase
    form_class = HorarioClaseForm
    title = "Nuevo horario de clase"
    success_url = reverse_lazy("academico:horario_list")
    cancel_url = reverse_lazy("academico:horario_list")


class HorarioClaseUpdateView(InstitutoUpdateView):
    model = HorarioClase
    form_class = HorarioClaseForm
    title = "Editar horario de clase"
    success_url = reverse_lazy("academico:horario_list")
    cancel_url = reverse_lazy("academico:horario_list")


class TemaListView(InstitutoListView):
    model = Tema
    title = "Temas"
    create_url_name = "academico:tema_nuevo"
    columns = (("Temario", "temario"), ("Orden", "orden"), ("Nombre", "nombre"), ("Dificultad", "dificultad"), ("Clases", "numero_clases"))

    def get_queryset(self):
        return super().get_queryset().select_related("temario", "temario__asignatura")


class TemaCreateView(InstitutoCreateView):
    model = Tema
    form_class = TemaForm
    title = "Nuevo tema"
    success_url = reverse_lazy("academico:tema_list")
    cancel_url = reverse_lazy("academico:tema_list")


class TemaUpdateView(InstitutoUpdateView):
    model = Tema
    form_class = TemaForm
    title = "Editar tema"
    success_url = reverse_lazy("academico:tema_list")
    cancel_url = reverse_lazy("academico:tema_list")


class PlanificacionClaseListView(InstitutoListView):
    model = PlanificacionClase
    title = "Planificacion de clases"
    create_url_name = "academico:planificacion_nueva"
    columns = (("Fecha", "fecha_planificada"), ("Docente", "docente"), ("Aula", "aula"), ("Asignatura", "asignatura"), ("Tema", "tema"), ("Estado", "estado"))

    def get_queryset(self):
        return super().get_queryset().select_related("docente", "aula", "asignatura", "tema", "empresa")


class PlanificacionClaseCreateView(InstitutoCreateView):
    model = PlanificacionClase
    form_class = PlanificacionClaseForm
    title = "Nueva planificacion"
    success_url = reverse_lazy("academico:planificacion_list")
    cancel_url = reverse_lazy("academico:planificacion_list")


class PlanificacionClaseUpdateView(InstitutoUpdateView):
    model = PlanificacionClase
    form_class = PlanificacionClaseForm
    title = "Editar planificacion"
    success_url = reverse_lazy("academico:planificacion_list")
    cancel_url = reverse_lazy("academico:planificacion_list")


class BancoPreguntaListView(InstitutoListView):
    model = BancoPregunta
    title = "Bancos de preguntas"
    create_url_name = "academico:banco_nuevo"
    columns = (("Asignatura", "asignatura"), ("Tema", "tema"), ("Tipo", "tipo"), ("Meta", "meta_preguntas"), ("Revisado", "revisado_coordinacion"))

    def get_queryset(self):
        return super().get_queryset().select_related("asignatura", "tema", "subtema", "empresa")


class BancoPreguntaCreateView(InstitutoCreateView):
    model = BancoPregunta
    form_class = BancoPreguntaForm
    title = "Nuevo banco de preguntas"
    success_url = reverse_lazy("academico:banco_list")
    cancel_url = reverse_lazy("academico:banco_list")


class BancoPreguntaUpdateView(InstitutoUpdateView):
    model = BancoPregunta
    form_class = BancoPreguntaForm
    title = "Editar banco de preguntas"
    success_url = reverse_lazy("academico:banco_list")
    cancel_url = reverse_lazy("academico:banco_list")


class PreguntaListView(InstitutoListView):
    model = Pregunta
    title = "Preguntas"
    create_url_name = "academico:pregunta_nueva"
    columns = (("Banco", "banco_pregunta"), ("Enunciado", "enunciado"), ("Dificultad", "dificultad"), ("Estado", "estado"), ("Creado por", "creado_por"))

    def get_queryset(self):
        return super().get_queryset().select_related("banco_pregunta", "creado_por")

    def get_column_value(self, obj, attr):
        value = super().get_column_value(obj, attr)
        if attr == "enunciado" and len(value) > 90:
            return f"{value[:90]}..."
        return value


class PreguntaCreateView(InstitutoCreateView):
    model = Pregunta
    form_class = PreguntaForm
    title = "Nueva pregunta"
    success_url = reverse_lazy("academico:pregunta_list")
    cancel_url = reverse_lazy("academico:pregunta_list")


class PreguntaUpdateView(InstitutoUpdateView):
    model = Pregunta
    form_class = PreguntaForm
    title = "Editar pregunta"
    success_url = reverse_lazy("academico:pregunta_list")
    cancel_url = reverse_lazy("academico:pregunta_list")
