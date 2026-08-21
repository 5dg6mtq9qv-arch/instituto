from django.db.models import Q
from django.urls import reverse_lazy

from apps.core.web_views import InstitutoCreateView, InstitutoListView, InstitutoUpdateView

from .forms import AulaForm, CursoForm, FichaInscripcionForm, PeriodoAcademicoForm
from .models import Aula, Curso, FichaInscripcion, PeriodoAcademico


class PeriodoAcademicoListView(InstitutoListView):
    model = PeriodoAcademico
    title = "Periodos academicos"
    create_url_name = "matricula:periodo_nuevo"
    columns = (("Nombre", "nombre"), ("Regimen", "regimen"), ("Inicio", "fecha_inicio"), ("Fin", "fecha_fin"), ("Estado", "estado"))


class PeriodoAcademicoCreateView(InstitutoCreateView):
    model = PeriodoAcademico
    form_class = PeriodoAcademicoForm
    title = "Nuevo periodo"
    success_url = reverse_lazy("matricula:periodo_list")
    cancel_url = reverse_lazy("matricula:periodo_list")


class PeriodoAcademicoUpdateView(InstitutoUpdateView):
    model = PeriodoAcademico
    form_class = PeriodoAcademicoForm
    title = "Editar periodo"
    success_url = reverse_lazy("matricula:periodo_list")
    cancel_url = reverse_lazy("matricula:periodo_list")


class CursoListView(InstitutoListView):
    model = Curso
    title = "Cursos"
    create_url_name = "matricula:curso_nuevo"
    columns = (("Nombre", "nombre"), ("Grado", "grado"), ("Carrera", "carrera"), ("Universidad", "universidad"), ("Activo", "activo"))


class CursoCreateView(InstitutoCreateView):
    model = Curso
    form_class = CursoForm
    title = "Nuevo curso"
    success_url = reverse_lazy("matricula:curso_list")
    cancel_url = reverse_lazy("matricula:curso_list")


class CursoUpdateView(InstitutoUpdateView):
    model = Curso
    form_class = CursoForm
    title = "Editar curso"
    success_url = reverse_lazy("matricula:curso_list")
    cancel_url = reverse_lazy("matricula:curso_list")


class AulaListView(InstitutoListView):
    model = Aula
    title = "Aulas"
    create_url_name = "matricula:aula_nueva"
    columns = (("Nombre", "nombre"), ("Seccion", "seccion"), ("Jornada", "jornada"), ("Horario", "horario"), ("Capacidad", "capacidad"))

    def get_queryset(self):
        return super().get_queryset().select_related("periodo_academico", "empresa")


class AulaCreateView(InstitutoCreateView):
    model = Aula
    form_class = AulaForm
    title = "Nueva aula"
    success_url = reverse_lazy("matricula:aula_list")
    cancel_url = reverse_lazy("matricula:aula_list")


class AulaUpdateView(InstitutoUpdateView):
    model = Aula
    form_class = AulaForm
    title = "Editar aula"
    success_url = reverse_lazy("matricula:aula_list")
    cancel_url = reverse_lazy("matricula:aula_list")


class FichaInscripcionListView(InstitutoListView):
    model = FichaInscripcion
    title = "Fichas de inscripcion"
    create_url_name = "matricula:ficha_nueva"
    columns = (
        ("Numero", "numero"),
        ("Fecha", "fecha"),
        ("Estudiante", "estudiante"),
        ("Representante", "representante"),
        ("Curso", "curso"),
        ("Saldo", "saldo"),
        ("Estado", "estado"),
    )

    def get_queryset(self):
        queryset = super().get_queryset().select_related("estudiante", "representante", "curso", "aula", "periodo_academico")
        q = self.request.GET.get("q")
        if q:
            queryset = queryset.filter(
                Q(numero__icontains=q)
                | Q(estudiante__nombre__icontains=q)
                | Q(estudiante__identificacion__icontains=q)
                | Q(representante__nombre__icontains=q)
            )
        return queryset


class FichaInscripcionCreateView(InstitutoCreateView):
    model = FichaInscripcion
    form_class = FichaInscripcionForm
    title = "Nueva ficha de inscripcion"
    success_url = reverse_lazy("matricula:ficha_list")
    cancel_url = reverse_lazy("matricula:ficha_list")


class FichaInscripcionUpdateView(InstitutoUpdateView):
    model = FichaInscripcion
    form_class = FichaInscripcionForm
    title = "Editar ficha de inscripcion"
    success_url = reverse_lazy("matricula:ficha_list")
    cancel_url = reverse_lazy("matricula:ficha_list")
