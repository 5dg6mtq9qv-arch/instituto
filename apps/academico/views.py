import calendar as calendar_module
import json
from io import BytesIO
from datetime import date, timedelta
from urllib.parse import urlencode

from django.http import HttpResponse
from django.urls import reverse_lazy
from django.db import connection, transaction
from django.db.models import Prefetch
from django.db.models import Count, Min, Q
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from apps.core.models import Empresa, Partner
from apps.core.web_views import InstitutoCreateView, InstitutoListView, InstitutoUpdateView
from apps.matricula.models import FichaInscripcion

from .forms import (
    AsignaturaForm,
    AulaForm,
    BancoPreguntaForm,
    ClaseEstudianteMovimientoForm,
    CursoForm,
    GrupoEstudianteBulkForm,
    HorarioDistribucionBaseForm,
    HorarioDistribucionItemForm,
    HorarioDistribucionFormSet,
    MateriaForm,
    PeriodoForm,
    HorarioAsignacionBaseForm,
    HorarioAsignacionFormSet,
    HorarioClaseForm,
    CoordinacionPlanificacionForm,
    CoordinacionTemaFormSet,
    DocenteClasePlanificacionForm,
    PlanificacionDocenteBaseForm,
    PlanificacionDocenteFormSet,
    PlanificacionClaseForm,
    PreguntaForm,
    TemaForm,
    TemarioForm,
)
from .models import (
    Asignatura,
    Aula,
    AulaCurso,
    BancoPregunta,
    Clase,
    ClaseAsistencia,
    ClaseEstudianteMovimiento,
    Curso,
    CursoPeriodo,
    Dia,
    Horario,
    HorarioAulaCurso,
    HorarioClase,
    GrupoEstudiante,
    HorarioDia,
    Materia,
    MateriaCurso,
    Periodo,
    PlanificacionClase,
    PlanificacionDocente,
    ProfesorMateriaCurso,
    Pregunta,
    Competencia,
    Estrategia,
    Recurso,
    ClaseRecurso,
    Tema,
    Temario,
)


def can_view_all_horarios(user):
    return user.is_superuser or user.groups.filter(name="Director").exists() or user.has_perm("academico.view_all_horarioclase")


def user_can_access_coordinacion(user):
    return user.is_superuser or user.groups.filter(name__in=["Coordinacion", "Direccion", "Director"]).exists()


UNASSIGNED_CLASS_ALERT_DAYS = 30
CLASS_ASSIGNMENT_LOCK_STATES = {"revision", "aprobada"}
CLASS_ASSIGNMENT_LOCK_MESSAGE = "La clase no se puede modificar porque tiene una planificacion enviada o aprobada."


def file_attachment_meta(file_field):
    if not file_field:
        return None
    name = str(file_field.name or "")
    filename = name.rsplit("/", 1)[-1]
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    file_types = {
        "pdf": {
            "extensions": {"pdf"},
            "icon": "ri-file-pdf-line",
            "label": "PDF",
        },
        "word": {
            "extensions": {"doc", "docx", "odt"},
            "icon": "ri-file-word-line",
            "label": "Word",
        },
        "excel": {
            "extensions": {"csv", "ods", "xls", "xlsx"},
            "icon": "ri-file-excel-line",
            "label": "Excel",
        },
        "ppt": {
            "extensions": {"odp", "ppt", "pptx"},
            "icon": "ri-file-ppt-line",
            "label": "Presentacion",
        },
        "image": {
            "extensions": {"gif", "jpeg", "jpg", "png", "svg", "webp"},
            "icon": "ri-file-image-line",
            "label": "Imagen",
        },
        "zip": {
            "extensions": {"7z", "gz", "rar", "tar", "zip"},
            "icon": "ri-file-zip-line",
            "label": "Comprimido",
        },
        "video": {
            "extensions": {"avi", "mkv", "mov", "mp4", "webm"},
            "icon": "ri-file-video-line",
            "label": "Video",
        },
        "audio": {
            "extensions": {"m4a", "mp3", "ogg", "wav"},
            "icon": "ri-file-music-line",
            "label": "Audio",
        },
        "text": {
            "extensions": {"md", "rtf", "txt"},
            "icon": "ri-file-text-line",
            "label": "Texto",
        },
    }
    for kind, config in file_types.items():
        if extension in config["extensions"]:
            return {
                "kind": kind,
                "icon": config["icon"],
                "label": config["label"],
                "filename": filename,
            }
    return {
        "kind": "file",
        "icon": "ri-file-line",
        "label": extension.upper() if extension else "Archivo",
        "filename": filename or "Archivo",
    }


def can_assign_docente(user):
    return (
        user.is_superuser
        or user.has_perm("academico.add_profesormateriacurso")
        or user.has_perm("academico.change_profesormateriacurso")
    )


def docente_responsable_filter(docente):
    return Q(docente_override=True, docente=docente) | Q(
        docente_override=False,
        materia_curso__profesor_materia_cursos__partner=docente,
    )


def docente_responsable_search_filter(query):
    return (
        Q(docente_override=True, docente__nombre__icontains=query)
        | Q(docente_override=True, docente__identificacion__icontains=query)
        | Q(
            docente_override=False,
            materia_curso__profesor_materia_cursos__partner__nombre__icontains=query,
        )
        | Q(
            docente_override=False,
            materia_curso__profesor_materia_cursos__partner__identificacion__icontains=query,
        )
    )


def get_clase_docentes(clase):
    if clase.docente_override:
        return [clase.docente] if clase.docente_id else []
    return [item.partner for item in clase.materia_curso.profesor_materia_cursos.all()]


def clase_tiene_docente(clase):
    if clase.docente_override:
        return bool(clase.docente_id)
    return clase.materia_curso.profesor_materia_cursos.exists()


def clases_sin_docente_queryset(curso=None, start_date=None, end_date=None):
    queryset = (
        Clase.objects.select_related(
            "materia_curso__materia",
            "materia_curso__grupo",
            "docente",
            "horario_aula_curso__aula_curso__aula",
            "horario_aula_curso__horario_dia__horario",
        )
        .filter(
            Q(docente_override=True, docente__isnull=True)
            | Q(docente_override=False, materia_curso__profesor_materia_cursos__isnull=True)
        )
        .distinct()
    )
    if curso:
        queryset = queryset.filter(materia_curso__grupo=curso)
    if start_date:
        queryset = queryset.filter(fecha__gte=start_date)
    if end_date:
        queryset = queryset.filter(fecha__lte=end_date)
    return queryset.order_by("fecha", "horario_aula_curso__horario_dia__horario__hora_inicio")


def clases_sin_docente_alert(curso=None, days=UNASSIGNED_CLASS_ALERT_DAYS, limit=6):
    today = timezone.localdate()
    queryset = clases_sin_docente_queryset(
        curso=curso,
        start_date=today,
        end_date=today + timedelta(days=days),
    )
    assign_url = reverse_lazy("academico:planificacion_docente")
    if curso:
        assign_url = f"{assign_url}?{urlencode({'grupo': curso.pk})}"
    return {
        "count": queryset.count(),
        "items": list(queryset[:limit]),
        "days": days,
        "assign_url": assign_url,
    }


class CoordinacionRequiredMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if not user_can_access_coordinacion(request.user):
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)


def readable_text_color(hex_color):
    color = (hex_color or "").lstrip("#")
    if len(color) != 6:
        return "#ffffff"
    try:
        red = int(color[0:2], 16)
        green = int(color[2:4], 16)
        blue = int(color[4:6], 16)
    except ValueError:
        return "#ffffff"
    brightness = (red * 299 + green * 587 + blue * 114) / 1000
    return "#111827" if brightness > 160 else "#ffffff"


def xlsx_color(hex_color):
    return (hex_color or "#2563eb").replace("#", "").upper()


SCHEDULE_EXPORT_COLUMN_WIDTH = 30
SCHEDULE_EXPORT_LINE_HEIGHT = 15
SCHEDULE_EXPORT_MIN_ROW_HEIGHT = 78
SCHEDULE_EXPORT_MAX_ROW_HEIGHT = 360


def estimated_schedule_wrapped_lines(value, column_width=SCHEDULE_EXPORT_COLUMN_WIDTH):
    line_count = 0
    wrap_width = max(1, column_width - 4)
    for line in str(value).splitlines() or [""]:
        line_count += max(1, (len(line) + wrap_width - 1) // wrap_width)
    return line_count


def schedule_export_row_height(line_count):
    calculated = line_count * SCHEDULE_EXPORT_LINE_HEIGHT + 10
    return max(SCHEDULE_EXPORT_MIN_ROW_HEIGHT, min(SCHEDULE_EXPORT_MAX_ROW_HEIGHT, calculated))


def safe_sheet_title(title):
    invalid = '[]:*?/\\'
    cleaned = "".join("_" if char in invalid else char for char in str(title or "Hoja"))
    return cleaned[:31] or "Hoja"


class CursoListView(InstitutoListView):
    model = Curso
    template_name = "academico/curso_list.html"
    title = "Cursos"
    create_url_name = "academico:curso_nuevo"
    update_url_name = "academico:curso_editar"
    columns = (
        ("Nombre", "nombre"),
        ("Activo", "activo"),
        ("Descripcion", "descripcion"),
    )

    def get_queryset(self):
        queryset = super().get_queryset()
        q = self.request.GET.get("q")
        if q:
            queryset = queryset.filter(Q(nombre__icontains=q) | Q(descripcion__icontains=q))
        return queryset


class CursoCreateView(InstitutoCreateView):
    model = Curso
    form_class = CursoForm
    template_name = "academico/curso_form.html"
    title = "Nuevo curso"
    success_url = reverse_lazy("academico:curso_list")
    cancel_url = reverse_lazy("academico:curso_list")

    def dispatch(self, request, *args, **kwargs):
        today = timezone.localdate()
        if not Periodo.objects.filter(fecha_fin__gte=today).exists():
            return render(
                request,
                "academico/curso_sin_periodo.html",
                {
                    "title": "Nuevo curso",
                    "periodo_create_url": reverse_lazy("academico:periodo_nuevo"),
                    "cancel_url": reverse_lazy("academico:curso_list"),
                },
            )
        return super().dispatch(request, *args, **kwargs)


class CursoUpdateView(InstitutoUpdateView):
    model = Curso
    form_class = CursoForm
    template_name = "academico/curso_form.html"
    title = "Editar curso"
    success_url = reverse_lazy("academico:curso_list")
    cancel_url = reverse_lazy("academico:curso_list")


class CursoToggleActivoView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "academico.change_curso"

    def post(self, request, pk):
        curso = get_object_or_404(Curso, pk=pk)
        curso.activo = not curso.activo
        curso.usuario_updated = request.user
        curso.save(update_fields=["activo", "updated_at", "usuario_updated"])
        estado = "activado" if curso.activo else "desactivado"
        messages.success(request, f"Curso {estado} correctamente.")
        return redirect("academico:curso_list")


class AulaListView(InstitutoListView):
    model = Aula
    template_name = "academico/aula_list.html"
    title = "Aulas"
    create_url_name = "academico:aula_nueva"
    update_url_name = "academico:aula_editar"
    columns = (
        ("Nombre", "nombre"),
        ("Descripcion", "descripcion"),
    )

    def get_queryset(self):
        queryset = super().get_queryset()
        q = self.request.GET.get("q")
        if q:
            queryset = queryset.filter(Q(nombre__icontains=q) | Q(descripcion__icontains=q))
        return queryset


class AulaCreateView(InstitutoCreateView):
    model = Aula
    form_class = AulaForm
    template_name = "academico/aula_form.html"
    title = "Nueva aula"
    success_url = reverse_lazy("academico:aula_list")
    cancel_url = reverse_lazy("academico:aula_list")


class AulaUpdateView(InstitutoUpdateView):
    model = Aula
    form_class = AulaForm
    template_name = "academico/aula_form.html"
    title = "Editar aula"
    success_url = reverse_lazy("academico:aula_list")
    cancel_url = reverse_lazy("academico:aula_list")


class MateriaListView(InstitutoListView):
    model = Materia
    template_name = "academico/materia_list.html"
    title = "Materias"
    create_url_name = "academico:materia_nueva"
    update_url_name = "academico:materia_editar"
    columns = (
        ("Nombre", "nombre"),
        ("Nombre corto", "nombre_corto"),
        ("Color", "color"),
        ("Descripcion", "descripcion"),
    )

    def get_queryset(self):
        queryset = super().get_queryset()
        q = self.request.GET.get("q")
        if q:
            queryset = queryset.filter(
                Q(nombre__icontains=q)
                | Q(nombre_corto__icontains=q)
                | Q(descripcion__icontains=q)
            )
        return queryset


class MateriaCreateView(InstitutoCreateView):
    model = Materia
    form_class = MateriaForm
    template_name = "academico/materia_form.html"
    title = "Nueva materia"
    success_url = reverse_lazy("academico:materia_list")
    cancel_url = reverse_lazy("academico:materia_list")


class MateriaUpdateView(InstitutoUpdateView):
    model = Materia
    form_class = MateriaForm
    template_name = "academico/materia_form.html"
    title = "Editar materia"
    success_url = reverse_lazy("academico:materia_list")
    cancel_url = reverse_lazy("academico:materia_list")


class PeriodoListView(InstitutoListView):
    model = Periodo
    template_name = "academico/periodo_list.html"
    title = "Periodos"
    create_url_name = "academico:periodo_nuevo"
    update_url_name = "academico:periodo_editar"
    columns = (
        ("Nombre", "nombre"),
        ("Inicio", "fecha_inicio"),
        ("Fin", "fecha_fin"),
    )

    def get_queryset(self):
        queryset = super().get_queryset()
        q = self.request.GET.get("q")
        if q:
            queryset = queryset.filter(Q(nombre__icontains=q))
        return queryset


class PeriodoCreateView(InstitutoCreateView):
    model = Periodo
    form_class = PeriodoForm
    template_name = "academico/periodo_form.html"
    title = "Nuevo periodo"
    success_url = reverse_lazy("academico:periodo_list")
    cancel_url = reverse_lazy("academico:periodo_list")


class PeriodoUpdateView(InstitutoUpdateView):
    model = Periodo
    form_class = PeriodoForm
    template_name = "academico/periodo_form.html"
    title = "Editar periodo"
    success_url = reverse_lazy("academico:periodo_list")
    cancel_url = reverse_lazy("academico:periodo_list")


class HorarioDistribucionListView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "academico.view_horarioaulacurso"
    template_name = "academico/horario_distribucion_list.html"

    def get(self, request, *args, **kwargs):
        q = request.GET.get("q")
        grupos = (
            Curso.objects.filter(aula_cursos__horario_aula_cursos__fecha__isnull=True)
            .annotate(total_horarios=Count("aula_cursos__horario_aula_cursos", distinct=True))
            .order_by("nombre")
            .distinct()
        )
        if q:
            grupos = grupos.filter(nombre__icontains=q)

        return render(
            request,
            self.template_name,
            {
                "title": "Horarios",
                "grupos": grupos,
                "can_edit": request.user.has_perm("academico.change_horarioaulacurso"),
                "create_url_name": "academico:horario_distribucion_nuevo"
                if request.user.has_perm("academico.add_horarioaulacurso")
                else "",
            },
        )


class HorarioDistribucionDetalleView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "academico.view_horarioaulacurso"
    template_name = "academico/horario_distribucion_detalle.html"

    def get(self, request, curso_pk):
        curso = get_object_or_404(Curso, pk=curso_pk)
        horarios = (
            HorarioAulaCurso.objects.select_related(
                "aula_curso__curso",
                "aula_curso__aula",
                "horario_dia__dia",
                "horario_dia__horario",
            )
            .order_by(
                "aula_curso__curso__nombre",
                "horario_dia__dia__id",
                "horario_dia__horario__hora_inicio",
                "aula_curso__aula__nombre",
            )
            .filter(aula_curso__curso=curso)
            .filter(fecha__isnull=True)
        )
        return render(
            request,
            self.template_name,
            {
                "title": "Detalle de horario",
                "curso": curso,
                "horarios": horarios,
                "can_edit": request.user.has_perm("academico.change_horarioaulacurso"),
            },
        )


class HorarioDistribucionCreateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "academico.add_horarioaulacurso"
    template_name = "academico/horario_distribucion_form.html"
    replace_existing = False

    def get(self, request, *args, **kwargs):
        curso = self.get_curso()
        base_initial = {"curso": curso.pk} if curso else None
        base_form = HorarioDistribucionBaseForm(initial=base_initial)
        formset = self.get_formset(curso=curso)
        return render(request, self.template_name, self.get_context(base_form, formset))

    def post(self, request, *args, **kwargs):
        base_form = HorarioDistribucionBaseForm(request.POST)
        formset = HorarioDistribucionFormSet(request.POST)
        if base_form.is_valid() and formset.is_valid():
            curso = base_form.cleaned_data["curso"]
            schedule_rows = [(form, form.cleaned_data) for form in formset if form.has_schedule_data()]
            if not schedule_rows:
                base_form.add_error(None, "Agrega al menos un horario.")
                return render(request, self.template_name, self.get_context(base_form, formset))
            if self.has_schedule_conflicts(curso, schedule_rows):
                return render(request, self.template_name, self.get_context(base_form, formset))

            saved = 0
            duplicates = 0
            with transaction.atomic():
                if self.replace_existing:
                    HorarioAulaCurso.objects.filter(aula_curso__curso=curso, fecha__isnull=True).delete()
                for _, row in schedule_rows:
                    aula = row["aula"]
                    dia = row["dia"]
                    hora_inicio = row["hora_inicio"]
                    hora_fin = row["hora_fin"]

                    aula_curso, _ = AulaCurso.objects.get_or_create(
                        aula=aula,
                        curso=curso,
                        defaults={"nombre": f"{aula} - {curso}"},
                    )
                    horario, _ = Horario.objects.get_or_create(
                        hora_inicio=hora_inicio,
                        hora_fin=hora_fin,
                    )
                    horario_dia, _ = HorarioDia.objects.get_or_create(
                        dia=dia,
                        horario=horario,
                    )
                    _, created = HorarioAulaCurso.objects.get_or_create(
                        aula_curso=aula_curso,
                        horario_dia=horario_dia,
                        fecha=None,
                    )
                    if created:
                        saved += 1
                    else:
                        duplicates += 1

            if saved:
                message = f"{saved} horario(s) asignado(s)."
                if duplicates:
                    message += f" {duplicates} ya existian."
                messages.success(request, message)
                return redirect(f"{reverse_lazy('academico:horario_distribucion')}?curso={curso.pk}")
            if duplicates:
                messages.info(request, f"{duplicates} horario(s) ya estaban asignados.")
                return redirect(f"{reverse_lazy('academico:horario_distribucion')}?curso={curso.pk}")
        return render(request, self.template_name, self.get_context(base_form, formset))

    def has_schedule_conflicts(self, curso, schedule_rows):
        has_conflicts = False
        seen = {}
        for form, row in schedule_rows:
            aula = row["aula"]
            dia = row["dia"]
            hora_inicio = row["hora_inicio"]
            hora_fin = row["hora_fin"]
            key = (aula.pk, dia.pk, hora_inicio, hora_fin)
            if key in seen:
                form.add_error("hora_inicio", f"Este horario esta repetido para {aula} el dia {dia}.")
                has_conflicts = True
                continue
            seen[key] = True

            conflict = (
                HorarioAulaCurso.objects.select_related(
                    "aula_curso__curso",
                    "horario_dia__horario",
                )
                .filter(
                    aula_curso__aula=aula,
                    fecha__isnull=True,
                    horario_dia__dia=dia,
                    horario_dia__horario__hora_inicio__lt=hora_fin,
                    horario_dia__horario__hora_fin__gt=hora_inicio,
                )
                .exclude(aula_curso__curso=curso)
                .first()
            )
            if conflict:
                horario = conflict.horario_dia.horario
                form.add_error(
                    "hora_inicio",
                    (
                        f"El horario de {hora_inicio:%H:%M} a {hora_fin:%H:%M} "
                        f"ya esta asignado al aula {aula} en el grupo "
                        f"{conflict.aula_curso.curso} de {horario.hora_inicio:%H:%M} "
                        f"a {horario.hora_fin:%H:%M}."
                    ),
                )
                has_conflicts = True
        return has_conflicts

    def get_curso(self):
        curso_pk = self.kwargs.get("curso_pk") or self.request.GET.get("curso")
        if not curso_pk:
            return None
        return get_object_or_404(Curso, pk=curso_pk)

    def get_formset(self, curso=None):
        initial = []
        if curso:
            horarios = (
                HorarioAulaCurso.objects.select_related(
                    "aula_curso__aula",
                    "horario_dia__dia",
                    "horario_dia__horario",
                )
                .filter(aula_curso__curso=curso)
                .filter(fecha__isnull=True)
                .order_by("horario_dia__dia__id", "horario_dia__horario__hora_inicio", "aula_curso__aula__nombre")
            )
            initial = [
                {
                    "aula": horario.aula_curso.aula,
                    "dia": horario.horario_dia.dia,
                    "hora_inicio": horario.horario_dia.horario.hora_inicio,
                    "hora_fin": horario.horario_dia.horario.hora_fin,
                }
                for horario in horarios
            ]
        return HorarioDistribucionFormSet(initial=initial or [{}])

    def get_context(self, base_form, formset):
        return {
            "title": "Nuevo horario",
            "base_form": base_form,
            "formset": formset,
            "cancel_url": reverse_lazy("academico:horario_distribucion"),
            "edit_url_template": "/academico/horario-distribucion/__curso__/editar/",
        }


class HorarioDistribucionUpdateView(HorarioDistribucionCreateView):
    permission_required = "academico.change_horarioaulacurso"
    replace_existing = True

    def get_context(self, base_form, formset):
        context = super().get_context(base_form, formset)
        context["title"] = "Editar horario"
        return context


class PlanificacionAcademicaView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "academico.view_clase"
    template_name = "academico/planificacion_academica.html"

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.get_context())

    def post(self, request, *args, **kwargs):
        action = request.POST.get("planning_action") or "assign_class"
        if action == "add_schedule":
            if not self.can_add_schedule(request.user):
                return self.handle_no_permission()
            return self.handle_add_schedule(request)
        if action == "update_schedule":
            if not self.can_add_schedule(request.user):
                return self.handle_no_permission()
            return self.handle_update_schedule(request)
        if action != "assign_class":
            messages.error(request, "Accion de planificacion no valida.")
            curso_id = self.get_request_curso_id(request)
            redirect_url = reverse_lazy("academico:planificacion_academica")
            if curso_id:
                redirect_url = f"{redirect_url}?curso={curso_id}"
            return redirect(redirect_url)
        if not self.can_save_class(request.user):
            return self.handle_no_permission()
        return self.handle_assign_class(request)

    def can_save_class(self, user):
        return user.is_superuser or user.has_perm("academico.add_clase") or user.has_perm("academico.change_clase")

    def can_add_schedule(self, user):
        return (
            user.is_superuser
            or user.has_perm("academico.add_horarioaulacurso")
            or user.has_perm("academico.change_horarioaulacurso")
        )

    def get_request_curso_id(self, request):
        return request.POST.get("curso") or request.GET.get("curso") or ""

    def get_request_curso(self, request):
        curso_id = self.get_request_curso_id(request)
        if not curso_id:
            return None
        try:
            return Curso.objects.filter(pk=curso_id).first()
        except (TypeError, ValueError):
            return None

    def redirect_to_planning(self, curso=None):
        redirect_url = reverse_lazy("academico:planificacion_academica")
        if curso:
            redirect_url = f"{redirect_url}?curso={curso.pk}"
        return redirect(redirect_url)

    def handle_add_schedule(self, request):
        curso = self.get_request_curso(request)
        if not curso:
            messages.error(request, "Selecciona un grupo valido para agregar el horario.")
            return self.redirect_to_planning()

        schedule_form = HorarioDistribucionItemForm(request.POST, prefix="schedule")
        generar_periodo = request.POST.get("generar_periodo", "on") == "on"
        fecha_horario, fecha_error = self.get_schedule_date(request)
        if schedule_form.is_valid():
            if fecha_error:
                schedule_form.add_error(None, fecha_error)
            elif not schedule_form.has_schedule_data():
                schedule_form.add_error(None, "Completa aula, dia y horas para agregar el horario.")
            else:
                curso_periodo = self.get_schedule_period(curso, fecha_horario)
                if not curso_periodo:
                    schedule_form.add_error(None, "La fecha seleccionada no pertenece a un periodo del grupo.")
                elif not generar_periodo and not fecha_horario:
                    schedule_form.add_error(None, "Selecciona un espacio del calendario para crear el horario puntual.")
                elif fecha_horario and schedule_form.cleaned_data["dia"].dia != self.weekday_to_dia()[fecha_horario.weekday()]:
                    schedule_form.add_error("dia", "La fecha seleccionada no corresponde al dia del horario.")
                elif self.has_schedule_overlap(schedule_form, generar_periodo, fecha_horario, curso_periodo):
                    pass
                else:
                    fecha_base = None if generar_periodo else fecha_horario
                    return self.save_schedule_block(request, curso, schedule_form, fecha_base)
        return render(request, self.template_name, self.get_context(schedule_form=schedule_form))

    def handle_update_schedule(self, request):
        curso = self.get_request_curso(request)
        if not curso:
            messages.error(request, "Selecciona un grupo valido para editar el horario.")
            return self.redirect_to_planning()

        schedule_id = request.POST.get("schedule_horario_aula_curso")
        try:
            horario_aula_curso = HorarioAulaCurso.objects.get(pk=schedule_id, aula_curso__curso=curso)
        except (HorarioAulaCurso.DoesNotExist, TypeError, ValueError):
            messages.error(request, "Selecciona un horario valido para editar.")
            return self.redirect_to_planning(curso)
        schedule_form = HorarioDistribucionItemForm(request.POST, prefix="schedule")
        generar_periodo = request.POST.get("generar_periodo", "on") == "on"
        fecha_horario, fecha_error = self.get_schedule_date(request)
        if schedule_form.is_valid():
            if fecha_error:
                schedule_form.add_error(None, fecha_error)
            elif not schedule_form.has_schedule_data():
                schedule_form.add_error(None, "Completa aula, dia y horas para editar el horario.")
            else:
                curso_periodo = self.get_schedule_period(curso, fecha_horario)
                fecha_base = None if generar_periodo else fecha_horario
                if not curso_periodo:
                    schedule_form.add_error(None, "La fecha seleccionada no pertenece a un periodo del grupo.")
                elif not generar_periodo and not fecha_horario:
                    schedule_form.add_error(None, "Selecciona una fecha para convertir el horario en puntual.")
                elif fecha_horario and schedule_form.cleaned_data["dia"].dia != self.weekday_to_dia()[fecha_horario.weekday()]:
                    schedule_form.add_error("dia", "La fecha seleccionada no corresponde al dia del horario.")
                elif self.has_schedule_edit_lock(schedule_form, horario_aula_curso, fecha_base):
                    pass
                elif self.has_schedule_overlap(
                    schedule_form,
                    generar_periodo,
                    fecha_horario,
                    curso_periodo,
                    exclude_schedule=horario_aula_curso,
                ):
                    pass
                else:
                    return self.update_schedule_block(request, curso, horario_aula_curso, schedule_form, fecha_base)
        return render(
            request,
            self.template_name,
            self.get_context(schedule_form=schedule_form, schedule_action="update_schedule"),
        )

    def get_schedule_date(self, request):
        fecha_value = request.POST.get("schedule_fecha") or ""
        if not fecha_value:
            return None, ""
        try:
            return date.fromisoformat(fecha_value), ""
        except ValueError:
            return None, "La fecha seleccionada no es valida."

    def get_schedule_period(self, curso, fecha_horario=None):
        periodos = CursoPeriodo.objects.select_related("periodo").filter(curso=curso)
        if fecha_horario:
            return periodos.filter(
                periodo__fecha_inicio__lte=fecha_horario,
                periodo__fecha_fin__gte=fecha_horario,
            ).first()
        return periodos.order_by("-periodo__fecha_inicio").first()

    def get_schedule_parts(self, curso, schedule_form):
        aula = schedule_form.cleaned_data["aula"]
        dia = schedule_form.cleaned_data["dia"]
        hora_inicio = schedule_form.cleaned_data["hora_inicio"]
        hora_fin = schedule_form.cleaned_data["hora_fin"]
        aula_curso, _ = AulaCurso.objects.get_or_create(
            aula=aula,
            curso=curso,
            defaults={"nombre": f"{aula} - {curso}"},
        )
        horario, _ = Horario.objects.get_or_create(
            hora_inicio=hora_inicio,
            hora_fin=hora_fin,
        )
        horario_dia, _ = HorarioDia.objects.get_or_create(
            dia=dia,
            horario=horario,
        )
        return aula_curso, horario_dia

    def save_schedule_block(self, request, curso, schedule_form, fecha_horario=None):
        with transaction.atomic():
            aula_curso, horario_dia = self.get_schedule_parts(curso, schedule_form)
            _, created = HorarioAulaCurso.objects.get_or_create(
                aula_curso=aula_curso,
                horario_dia=horario_dia,
                fecha=fecha_horario,
            )
        if created:
            if fecha_horario:
                messages.success(request, "Horario agregado solo para la fecha seleccionada.")
            else:
                messages.success(request, "Horario agregado al calendario del grupo.")
        else:
            messages.info(request, "Ese horario ya estaba agregado al grupo.")
        return self.redirect_to_planning(curso)

    def update_schedule_block(self, request, curso, horario_aula_curso, schedule_form, fecha_horario=None):
        with transaction.atomic():
            aula_curso, horario_dia = self.get_schedule_parts(curso, schedule_form)
            horario_aula_curso.aula_curso = aula_curso
            horario_aula_curso.horario_dia = horario_dia
            horario_aula_curso.fecha = fecha_horario
            horario_aula_curso.save(update_fields=["aula_curso", "horario_dia", "fecha"])
        messages.success(request, "Horario actualizado correctamente.")
        return self.redirect_to_planning(curso)

    def weekday_to_dia(self):
        return {
            0: "Lunes",
            1: "Martes",
            2: "Miercoles",
            3: "Jueves",
            4: "Viernes",
            5: "Sabado",
            6: "Domingo",
        }

    def period_dates_for_day(self, periodo, dia_name):
        weekday_lookup = {name: weekday for weekday, name in self.weekday_to_dia().items()}
        target_weekday = weekday_lookup.get(dia_name)
        if target_weekday is None:
            return []
        dates = []
        current_date = periodo.fecha_inicio
        while current_date <= periodo.fecha_fin:
            if current_date.weekday() == target_weekday:
                dates.append(current_date)
            current_date += timedelta(days=1)
        return dates

    def has_schedule_edit_lock(self, schedule_form, horario_aula_curso, fecha_horario):
        clases = Clase.objects.filter(horario_aula_curso=horario_aula_curso)
        if clases.filter(estado_planificacion__in=CLASS_ASSIGNMENT_LOCK_STATES).exists():
            schedule_form.add_error(None, "No se puede modificar el horario porque tiene una planificacion enviada o aprobada.")
            return True
        if clases.filter(fecha__lt=timezone.localdate()).exists():
            schedule_form.add_error(None, "No se puede modificar el horario porque tiene clases anteriores a hoy.")
            return True
        day_changed = horario_aula_curso.horario_dia.dia_id != schedule_form.cleaned_data["dia"].pk
        scope_changed = horario_aula_curso.fecha != fecha_horario
        if (day_changed or scope_changed) and clases.exists():
            schedule_form.add_error(
                None,
                "No se puede cambiar el dia o alcance de un horario que ya tiene clases planificadas.",
            )
            return True
        return False

    def has_schedule_overlap(self, schedule_form, generar_periodo, fecha_horario, curso_periodo, exclude_schedule=None):
        aula = schedule_form.cleaned_data["aula"]
        dia = schedule_form.cleaned_data["dia"]
        hora_inicio = schedule_form.cleaned_data["hora_inicio"]
        hora_fin = schedule_form.cleaned_data["hora_fin"]
        conflicts = HorarioAulaCurso.objects.select_related(
            "aula_curso__curso",
            "horario_dia__horario",
        ).filter(
            aula_curso__aula=aula,
            horario_dia__dia=dia,
            horario_dia__horario__hora_inicio__lt=hora_fin,
            horario_dia__horario__hora_fin__gt=hora_inicio,
        )
        if exclude_schedule:
            conflicts = conflicts.exclude(pk=exclude_schedule.pk)
        if generar_periodo:
            period_dates = self.period_dates_for_day(curso_periodo.periodo, dia.dia)
            conflicts = conflicts.filter(Q(fecha__isnull=True) | Q(fecha__in=period_dates))
        else:
            conflicts = conflicts.filter(Q(fecha__isnull=True) | Q(fecha=fecha_horario))

        conflict = conflicts.first()
        if not conflict:
            return False

        horario = conflict.horario_dia.horario
        fecha_label = f" el {conflict.fecha:%d/%m/%Y}" if conflict.fecha else " en el periodo"
        schedule_form.add_error(
            "hora_inicio",
            (
                f"El aula {aula} ya esta asignada al grupo {conflict.aula_curso.curso} "
                f"{fecha_label} de {horario.hora_inicio:%H:%M} a {horario.hora_fin:%H:%M}."
            ),
        )
        return True

    def handle_assign_class(self, request):
        curso = self.get_request_curso(request)
        if not curso:
            messages.error(request, "Selecciona un grupo valido para asignar la clase.")
            return self.redirect_to_planning()

        horario_id = request.POST.get("horario_aula_curso")
        if horario_id:
            fecha_value = request.POST.get("fecha") or ""
            horario_aula_curso = get_object_or_404(
                HorarioAulaCurso,
                pk=horario_id,
                aula_curso__curso=curso,
            )
            try:
                fecha_clase = date.fromisoformat(fecha_value)
            except ValueError:
                messages.error(request, "La fecha seleccionada no es valida.")
                return redirect(f"{reverse_lazy('academico:planificacion_academica')}?curso={curso.pk}")

            curso_periodo = (
                CursoPeriodo.objects.select_related("periodo")
                .filter(curso=curso, periodo__fecha_inicio__lte=fecha_clase, periodo__fecha_fin__gte=fecha_clase)
                .first()
            )
            weekday_to_dia = self.weekday_to_dia()
            if (
                not curso_periodo
                or horario_aula_curso.horario_dia.dia.dia != weekday_to_dia[fecha_clase.weekday()]
                or (horario_aula_curso.fecha and horario_aula_curso.fecha != fecha_clase)
            ):
                messages.error(request, "La fecha seleccionada no corresponde al horario del grupo.")
                return redirect(f"{reverse_lazy('academico:planificacion_academica')}?curso={curso.pk}")

            materia_id = request.POST.get("materia") or ""
            docente_value = request.POST.get("docente") or ""
            asignar_periodo = request.POST.get("asignar_periodo") == "on" and not horario_aula_curso.fecha
            today = timezone.localdate()
            if fecha_clase < today:
                messages.error(request, "No se puede modificar una clase con fecha anterior a hoy.")
                return redirect(f"{reverse_lazy('academico:planificacion_academica')}?curso={curso.pk}")
            selected_clase = Clase.objects.filter(horario_aula_curso=horario_aula_curso, fecha=fecha_clase).first()
            if selected_clase and selected_clase.estado_planificacion in CLASS_ASSIGNMENT_LOCK_STATES and not asignar_periodo:
                messages.error(request, CLASS_ASSIGNMENT_LOCK_MESSAGE)
                return redirect(f"{reverse_lazy('academico:planificacion_academica')}?curso={curso.pk}")
            if docente_value and not materia_id:
                messages.error(request, "Asigna una materia antes de asignar docente.")
                return redirect(f"{reverse_lazy('academico:planificacion_academica')}?curso={curso.pk}")

            materia_grupo = None
            if materia_id:
                materia = get_object_or_404(Materia, pk=materia_id)
                materia_grupo, _ = MateriaCurso.objects.get_or_create(
                    materia=materia,
                    grupo=curso,
                )
            docente = None
            docente_override = bool(docente_value)
            if docente_value and docente_value != "__none__":
                docente = get_object_or_404(Partner, pk=docente_value, es_docente=True, activo=True)

            with transaction.atomic():
                updated_count, locked_count = self.apply_clase_assignment(
                    horario_aula_curso,
                    fecha_clase,
                    materia_grupo,
                    docente,
                    docente_override,
                )
                if asignar_periodo:
                    current_date = max(fecha_clase, today)
                    while current_date <= curso_periodo.periodo.fecha_fin:
                        if (
                            current_date != fecha_clase
                            and weekday_to_dia[current_date.weekday()] == horario_aula_curso.horario_dia.dia.dia
                        ):
                            updated, locked = self.apply_clase_assignment(
                                horario_aula_curso,
                                current_date,
                                materia_grupo,
                                docente,
                                docente_override,
                            )
                            updated_count += updated
                            locked_count += locked
                        current_date += timedelta(days=1)
                    action = "asignada" if materia_grupo else "removida"
                    if updated_count:
                        messages.success(request, f"Clase {action} correctamente desde la fecha seleccionada en {updated_count} fecha(s) editable(s).")
                    if locked_count:
                        messages.warning(
                            request,
                            f"{locked_count} clase(s) no se modificaron porque tienen una planificacion enviada o aprobada.",
                        )
                    if not updated_count and not locked_count:
                        messages.info(request, "No habia clases editables para modificar en este horario.")
                elif locked_count:
                    messages.error(request, CLASS_ASSIGNMENT_LOCK_MESSAGE)
                elif materia_grupo:
                    messages.success(request, "Clase actualizada correctamente.")
                else:
                    messages.success(request, "Clase removida correctamente.")
            return redirect(f"{reverse_lazy('academico:planificacion_academica')}?curso={curso.pk}")

        messages.error(request, "Selecciona un horario del calendario para asignar la clase.")
        return redirect(f"{reverse_lazy('academico:planificacion_academica')}?curso={curso.pk}")

    def apply_clase_assignment(self, horario_aula_curso, fecha_clase, materia_grupo, docente=None, docente_override=False):
        clase = Clase.objects.filter(horario_aula_curso=horario_aula_curso, fecha=fecha_clase).first()
        if clase and clase.estado_planificacion in CLASS_ASSIGNMENT_LOCK_STATES:
            return 0, 1
        if not materia_grupo:
            if clase:
                self.delete_clase_assignment(clase)
                return 1, 0
            return 0, 0
        if not clase:
            Clase.objects.create(
                horario_aula_curso=horario_aula_curso,
                materia_curso=materia_grupo,
                docente=docente,
                docente_override=docente_override,
                fecha=fecha_clase,
            )
            return 1, 0
        update_fields = []
        if clase.materia_curso_id != materia_grupo.pk:
            reset_fields = self.reset_clase_planificacion(clase)
            clase.materia_curso = materia_grupo
            update_fields.extend(["materia_curso", *reset_fields])
        docente_id = docente.pk if docente else None
        if clase.docente_id != docente_id:
            clase.docente = docente
            update_fields.append("docente")
        if clase.docente_override != docente_override:
            clase.docente_override = docente_override
            update_fields.append("docente_override")
        if update_fields:
            clase.save(update_fields=update_fields)
        return 1, 0

    def delete_clase_assignment(self, clase):
        self.clear_clase_relations(clase)
        clase.delete()

    def reset_clase_planificacion(self, clase):
        self.clear_clase_relations(clase)
        clase.tema = None
        clase.subtema = None
        clase.descripcion = ""
        clase.estado_planificacion = "pendiente"
        clase.notas_revision = ""
        clase.observaciones_revision = {}
        clase.revisado_por = None
        clase.fecha_revision = None
        clase.asistencia_cerrada = False
        clase.asistencia_cerrada_por = None
        clase.fecha_cierre_asistencia = None
        clase.revision_tema_ok = False
        clase.revision_detalle_ok = False
        clase.revision_competencias_ok = False
        clase.revision_estrategias_ok = False
        clase.revision_recursos_ok = False
        return [
            "tema",
            "subtema",
            "descripcion",
            "estado_planificacion",
            "notas_revision",
            "observaciones_revision",
            "revisado_por",
            "fecha_revision",
            "asistencia_cerrada",
            "asistencia_cerrada_por",
            "fecha_cierre_asistencia",
            "revision_tema_ok",
            "revision_detalle_ok",
            "revision_competencias_ok",
            "revision_estrategias_ok",
            "revision_recursos_ok",
        ]

    def clear_clase_relations(self, clase):
        clase.competencias.clear()
        clase.estrategias.clear()
        ClaseRecurso.objects.filter(clase=clase).delete()
        ClaseAsistencia.objects.filter(clase=clase).delete()
        ClaseEstudianteMovimiento.objects.filter(Q(clase_origen=clase) | Q(clase_destino=clase)).delete()
        self.delete_legacy_clase_recursos(clase.pk)

    def delete_legacy_clase_recursos(self, clase_id):
        if connection.vendor != "postgresql":
            return
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'academico'
                  AND table_name = 'clase_recursos'
                """
            )
            if cursor.fetchone():
                cursor.execute("DELETE FROM academico.clase_recursos WHERE clase_id = %s", [clase_id])

    def get_context(self, schedule_form=None, schedule_action=None):
        cursos = Curso.objects.filter(activo=True).order_by("nombre")
        materias = list(Materia.objects.order_by("nombre"))
        docentes = list(Partner.objects.filter(es_docente=True, activo=True).order_by("nombre"))
        selected_curso_id = self.request.GET.get("curso") or self.request.POST.get("curso") or ""
        selected_curso = None
        selected_curso_periodo = None
        unassigned_alert = clases_sin_docente_alert()
        rows = []
        calendar_events = []
        calendar_default_date = timezone.localdate().isoformat()
        schedule_form = schedule_form or HorarioDistribucionItemForm(prefix="schedule")
        dias_by_name = {item.dia: item.pk for item in Dia.objects.all()}
        weekday_dia_ids = {
            0: dias_by_name.get("Domingo"),
            1: dias_by_name.get("Lunes"),
            2: dias_by_name.get("Martes"),
            3: dias_by_name.get("Miercoles"),
            4: dias_by_name.get("Jueves"),
            5: dias_by_name.get("Viernes"),
            6: dias_by_name.get("Sabado"),
        }
        dia_labels = {str(pk): name for name, pk in dias_by_name.items() if pk}
        schedule_period_enabled = True
        if schedule_form.is_bound:
            schedule_period_enabled = self.request.POST.get("generar_periodo", "on") == "on"
        schedule_action = schedule_action or self.request.POST.get("planning_action") or "add_schedule"
        if schedule_action not in {"add_schedule", "update_schedule"}:
            schedule_action = "add_schedule"

        if selected_curso_id:
            try:
                selected_curso = Curso.objects.filter(pk=selected_curso_id).first()
            except (TypeError, ValueError):
                selected_curso = None
        if selected_curso_id and not selected_curso:
            selected_curso_id = ""
        if selected_curso:
            unassigned_alert = clases_sin_docente_alert(curso=selected_curso)
            selected_curso_periodo = (
                CursoPeriodo.objects.select_related("periodo")
                .filter(curso=selected_curso)
                .order_by("-periodo__fecha_inicio")
                .first()
            )
            horarios = HorarioAulaCurso.objects.select_related(
                "aula_curso__aula",
                "aula_curso__curso",
                "horario_dia__dia",
                "horario_dia__horario",
            ).filter(aula_curso__curso=selected_curso)
            if selected_curso_periodo:
                periodo = selected_curso_periodo.periodo
                horarios = horarios.filter(Q(fecha__isnull=True) | Q(fecha__gte=periodo.fecha_inicio, fecha__lte=periodo.fecha_fin))
            else:
                horarios = horarios.filter(fecha__isnull=True)
            horarios = list(
                horarios.order_by(
                    "horario_dia__horario__hora_inicio",
                    "horario_dia__horario__hora_fin",
                    "horario_dia__dia__id",
                    "fecha",
                    "aula_curso__aula__nombre",
                )
            )
            clases = {}
            docentes_by_materia_curso = {}
            if selected_curso_periodo:
                clases = {
                    (item.horario_aula_curso_id, item.fecha): item
                    for item in Clase.objects.select_related("materia_curso__materia", "docente").filter(
                        horario_aula_curso__in=horarios,
                        fecha__gte=selected_curso_periodo.periodo.fecha_inicio,
                        fecha__lte=selected_curso_periodo.periodo.fecha_fin,
                    )
                }
                for item in ProfesorMateriaCurso.objects.select_related("partner").filter(
                    materia_curso__grupo=selected_curso,
                ):
                    docentes_by_materia_curso.setdefault(item.materia_curso_id, []).append(item.partner)

            if selected_curso_periodo:
                weekday_to_dia = self.weekday_to_dia()
                current_date = selected_curso_periodo.periodo.fecha_inicio
                end_date = selected_curso_periodo.periodo.fecha_fin
                today = timezone.localdate()
                calendar_default_date = current_date.isoformat()
                while current_date <= end_date:
                    day_name = weekday_to_dia[current_date.weekday()]
                    blocks = []
                    for horario_aula_curso in horarios:
                        if horario_aula_curso.horario_dia.dia.dia != day_name:
                            continue
                        if horario_aula_curso.fecha and horario_aula_curso.fecha != current_date:
                            continue

                        horario = horario_aula_curso.horario_dia.horario
                        clase = clases.get((horario_aula_curso.pk, current_date))
                        materia_id = clase.materia_curso.materia_id if clase else None
                        materia = next((item for item in materias if item.pk == materia_id), None)
                        clase_docentes = []
                        if clase:
                            if clase.docente_override:
                                clase_docentes = [clase.docente] if clase.docente_id else []
                            else:
                                clase_docentes = docentes_by_materia_curso.get(clase.materia_curso_id, [])
                        docente_label = ", ".join(docente.nombre for docente in clase_docentes)
                        sin_docente = bool(clase and materia and not clase_docentes)
                        event_color = "#fef3c7" if sin_docente else (materia.color if materia else "#dff1ff")
                        title_parts = [
                            str(horario_aula_curso.aula_curso.aula),
                            getattr(materia, "nombre_corto", None) or getattr(materia, "nombre", "Sin materia"),
                        ]
                        if docente_label:
                            title_parts.append(docente_label)
                        elif sin_docente:
                            title_parts.append("Sin docente asignado")

                        planning_locked = bool(clase and clase.estado_planificacion in CLASS_ASSIGNMENT_LOCK_STATES)
                        single_date = bool(horario_aula_curso.fecha)
                        class_name = "materia-event sin-docente-event" if sin_docente else ("materia-event" if materia else "sin-materia-event")
                        if single_date:
                            class_name = f"{class_name} single-date-event"
                        is_past_date = current_date < today
                        editable_date = not is_past_date and not planning_locked
                        if is_past_date:
                            class_name = f"{class_name} fecha-pasada-event"
                        if planning_locked:
                            class_name = f"{class_name} approved-locked-event"
                        locked_reason = ""
                        if planning_locked:
                            locked_reason = CLASS_ASSIGNMENT_LOCK_MESSAGE
                        elif is_past_date:
                            locked_reason = "No se puede modificar una clase con fecha anterior a hoy."

                        blocks.append(
                            {
                                "id": horario_aula_curso.pk,
                                "aula": horario_aula_curso.aula_curso.aula,
                                "hora": f"{horario.hora_inicio:%H:%M} - {horario.hora_fin:%H:%M}",
                                "materia_id": materia_id,
                            }
                        )
                        calendar_events.append(
                            {
                                "id": f"{horario_aula_curso.pk}-{current_date.isoformat()}",
                                "horarioId": horario_aula_curso.pk,
                                "fecha": current_date.isoformat(),
                                "title": " · ".join(title_parts),
                                "start": f"{current_date.isoformat()}T{horario.hora_inicio:%H:%M:%S}",
                                "end": f"{current_date.isoformat()}T{horario.hora_fin:%H:%M:%S}",
                                "allDay": False,
                                "className": class_name,
                                "color": event_color,
                                "backgroundColor": event_color,
                                "borderColor": "#f59e0b" if sin_docente else event_color,
                                "textColor": "#92400e" if sin_docente else (readable_text_color(event_color) if materia else "#7c3aed"),
                                "aula": str(horario_aula_curso.aula_curso.aula),
                                "aulaId": horario_aula_curso.aula_curso.aula_id,
                                "diaId": horario_aula_curso.horario_dia.dia_id,
                                "hora": f"{horario.hora_inicio:%H:%M} - {horario.hora_fin:%H:%M}",
                                "horaInicio": f"{horario.hora_inicio:%H:%M}",
                                "horaFin": f"{horario.hora_fin:%H:%M}",
                                "materiaId": materia_id or "",
                                "materia": getattr(materia, "nombre", "") if materia else "",
                                "docenteId": self.get_docente_field_value(clase),
                                "docente": docente_label or ("Sin docente asignado" if sin_docente else ""),
                                "editableDate": editable_date,
                                "lockedReason": locked_reason,
                                "singleDate": single_date,
                                "scope": "Solo esta fecha" if single_date else "Todo el periodo",
                            }
                        )
                    if blocks:
                        rows.append({"fecha": current_date, "dia": day_name, "blocks": blocks})
                    current_date += timedelta(days=1)

        return {
            "title": "Planificacion academica",
            "periodo_create_url": reverse_lazy("academico:periodo_nuevo"),
            "cursos": cursos,
            "materias": materias,
            "docentes": docentes,
            "rows": rows,
            "calendar_events_json": json.dumps(calendar_events),
            "calendar_default_date": calendar_default_date,
            "selected_curso": selected_curso,
            "selected_curso_periodo": selected_curso_periodo,
            "selected_curso_id": selected_curso_id,
            "schedule_form": schedule_form,
            "schedule_form_has_errors": schedule_form.is_bound and bool(schedule_form.errors),
            "schedule_action": schedule_action,
            "schedule_edit_id": self.request.POST.get("schedule_horario_aula_curso", ""),
            "schedule_date_value": self.request.POST.get("schedule_fecha", ""),
            "weekday_dia_ids_json": json.dumps(weekday_dia_ids),
            "dia_labels_json": json.dumps(dia_labels),
            "schedule_period_enabled": schedule_period_enabled,
            "unassigned_alert": unassigned_alert,
            "can_save": self.can_save_class(self.request.user),
            "can_add_schedule": self.can_add_schedule(self.request.user),
        }

    def get_docente_field_value(self, clase):
        if not clase or not clase.docente_override:
            return ""
        return clase.docente_id or "__none__"


class PlanificacionAcademicaExportView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "academico.view_clase"

    weekday_headers = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]

    def get(self, request):
        export_type = request.GET.get("tipo") or "general"
        rows = self.get_rows()
        workbook = Workbook()
        workbook.remove(workbook.active)

        if export_type == "docente":
            grouped = self.group_rows(rows, lambda row: row["docente"] or "Sin docente asignado")
            filename = "horarios_por_docente.xlsx"
        elif export_type == "aula":
            grouped = self.group_rows(rows, lambda row: row["aula"] or "Sin aula")
            filename = "horarios_por_aula.xlsx"
        else:
            grouped = {"General": rows}
            filename = "horarios_general.xlsx"

        for title, sheet_rows in grouped.items():
            self.write_sheet(workbook, title, sheet_rows)

        if not grouped:
            self.write_sheet(workbook, "General", [])

        output = BytesIO()
        workbook.save(output)
        output.seek(0)
        response = HttpResponse(
            output.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    def get_rows(self):
        queryset = (
            Clase.objects.select_related(
                "materia_curso__materia",
                "materia_curso__grupo",
                "docente",
                "horario_aula_curso__aula_curso__aula",
                "horario_aula_curso__horario_dia__dia",
                "horario_aula_curso__horario_dia__horario",
            )
            .order_by(
                "fecha",
                "horario_aula_curso__horario_dia__horario__hora_inicio",
                "materia_curso__grupo__nombre",
            )
        )
        curso_id = self.request.GET.get("curso")
        if curso_id:
            queryset = queryset.filter(materia_curso__grupo_id=curso_id)

        docentes = {}
        for item in ProfesorMateriaCurso.objects.select_related("partner", "materia_curso"):
            docentes.setdefault(item.materia_curso_id, []).append(item.partner.nombre)
        rows = []
        for clase in queryset:
            horario = clase.horario_aula_curso.horario_dia.horario
            materia = clase.materia_curso.materia
            if clase.docente_override:
                docente_label = clase.docente.nombre if clase.docente_id else ""
            else:
                docente_label = ", ".join(docentes.get(clase.materia_curso_id, []))
            rows.append(
                {
                    "fecha": clase.fecha,
                    "dia": clase.horario_aula_curso.horario_dia.dia.dia,
                    "hora": f"{horario.hora_inicio:%H:%M} - {horario.hora_fin:%H:%M}",
                    "grupo": clase.materia_curso.grupo.nombre,
                    "aula": str(clase.horario_aula_curso.aula_curso.aula),
                    "materia": materia.nombre,
                    "docente": docente_label or "Sin docente asignado",
                    "color": materia.color,
                }
            )
        return rows

    def group_rows(self, rows, key_func):
        grouped = {}
        for row in rows:
            grouped.setdefault(key_func(row), []).append(row)
        return dict(sorted(grouped.items(), key=lambda item: item[0]))

    def write_sheet(self, workbook, title, rows):
        sheet = workbook.create_sheet(safe_sheet_title(title))
        title_fill = PatternFill("solid", fgColor="DCEBFF")
        header_fill = PatternFill("solid", fgColor="4F81BD")
        time_fill = PatternFill("solid", fgColor="5B9BD5")
        thin = Side(style="thin", color="D7DEE8")
        border = Border(left=thin, right=thin, top=thin, bottom=thin)
        center = Alignment(horizontal="center", vertical="center", wrap_text=True)
        schedule_alignment = Alignment(horizontal="center", vertical="top", wrap_text=True)

        sheet.merge_cells(start_row=1, start_column=1, end_row=1, end_column=8)
        title_cell = sheet.cell(row=1, column=1, value=f"Horario - {title}")
        title_cell.font = Font(bold=True, size=14, color="111827")
        title_cell.fill = title_fill
        title_cell.alignment = center

        current_row = 3
        for week_start, week_rows in self.group_rows_by_week(rows).items():
            week_end = week_start + timedelta(days=6)
            sheet.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=8)
            week_cell = sheet.cell(
                row=current_row,
                column=1,
                value=f"Semana {week_start:%d/%m/%Y} - {week_end:%d/%m/%Y}",
            )
            week_cell.font = Font(bold=True, color="111827")
            week_cell.fill = title_fill
            week_cell.alignment = center
            current_row += 1

            sheet.cell(row=current_row, column=1, value="Hora")
            for col, day in enumerate(self.weekday_headers, start=2):
                sheet.cell(row=current_row, column=col, value=day)
            for col in range(1, 9):
                cell = sheet.cell(row=current_row, column=col)
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = header_fill
                cell.border = border
                cell.alignment = center
            current_row += 1

            time_slots = sorted({row["hora"] for row in week_rows})
            week_matrix = {}
            for row in week_rows:
                week_matrix.setdefault((row["hora"], row["fecha"].weekday()), []).append(row)
            for time_slot in time_slots:
                time_cell = sheet.cell(row=current_row, column=1, value=time_slot)
                time_cell.font = Font(bold=True, color="FFFFFF")
                time_cell.fill = time_fill
                time_cell.border = border
                time_cell.alignment = center
                max_lines = 1
                for weekday in range(7):
                    cell = sheet.cell(row=current_row, column=weekday + 2)
                    entries = week_matrix.get((time_slot, weekday), [])
                    if entries:
                        cell.value = "\n\n".join(self.schedule_label(item) for item in entries)
                        cell.fill = PatternFill("solid", fgColor=xlsx_color(entries[0]["color"]))
                        cell.font = Font(
                            color=xlsx_color(readable_text_color(entries[0]["color"])),
                            bold=True,
                            size=9,
                        )
                        max_lines = max(max_lines, estimated_schedule_wrapped_lines(cell.value))
                    else:
                        cell.value = ""
                        cell.fill = PatternFill("solid", fgColor="FFFFFF")
                    cell.border = border
                    cell.alignment = schedule_alignment
                sheet.row_dimensions[current_row].height = schedule_export_row_height(max_lines)
                current_row += 1

            current_row += 2

        if not rows:
            sheet.cell(row=3, column=1, value="Sin horarios registrados.")

        widths = [18] + [SCHEDULE_EXPORT_COLUMN_WIDTH] * 7
        for col, width in enumerate(widths, start=1):
            sheet.column_dimensions[get_column_letter(col)].width = width
        sheet.freeze_panes = "B5"

    def group_rows_by_week(self, rows):
        grouped = {}
        for row in rows:
            week_start = row["fecha"] - timedelta(days=row["fecha"].weekday())
            grouped.setdefault(week_start, []).append(row)
        return dict(sorted(grouped.items(), key=lambda item: item[0]))

    def schedule_label(self, row):
        parts = [row["materia"], row["grupo"], row["aula"]]
        if row["docente"]:
            parts.append(row["docente"])
        return "\n".join(parts)


class PlanificacionDocenteListView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "academico.view_profesormateriacurso"
    template_name = "academico/planificacion_docente_list.html"

    def get(self, request):
        cursos = list(Curso.objects.filter(activo=True).order_by("nombre"))
        selected_group = self.get_selected_group(cursos)
        q = (request.GET.get("q") or "").strip()
        asignaciones = self.get_asignaciones()
        if selected_group:
            asignaciones = asignaciones.filter(grupo=selected_group)
        else:
            asignaciones = asignaciones.none()
        if q:
            asignaciones = asignaciones.filter(
                Q(grupo__nombre__icontains=q)
                | Q(materia__nombre__icontains=q)
                | Q(materia__nombre_corto__icontains=q)
                | Q(profesor_materia_cursos__partner__nombre__icontains=q)
                | Q(profesor_materia_cursos__partner__identificacion__icontains=q)
            )
        asignaciones = list(asignaciones.distinct())
        grupos = self.group_asignaciones(asignaciones)
        active_group_summary = grupos[0] if grupos else self.empty_group_summary(selected_group)
        stats = self.get_stats(asignaciones)
        return render(
            request,
            self.template_name,
            {
                "title": "Planificacion docente",
                "docentes_disponibles": Partner.objects.filter(es_docente=True, activo=True).order_by("nombre"),
                "group_tabs": self.get_group_tabs(cursos, selected_group, q),
                "selected_group": selected_group,
                "active_group_summary": active_group_summary,
                "assignment_groups": grupos,
                "stats": stats,
                "unassigned_alert": clases_sin_docente_alert(curso=selected_group) if selected_group else clases_sin_docente_alert(),
                "can_assign_docente": can_assign_docente(request.user),
            },
        )

    def post(self, request):
        if not can_assign_docente(request.user):
            return self.handle_no_permission()

        materia_curso = get_object_or_404(
            MateriaCurso.objects.select_related("grupo", "materia"),
            pk=request.POST.get("materia_curso"),
        )
        docente_id = request.POST.get("docente") or ""
        with transaction.atomic():
            if docente_id:
                docente = get_object_or_404(Partner, pk=docente_id, es_docente=True, activo=True)
                ProfesorMateriaCurso.objects.filter(materia_curso=materia_curso).exclude(partner=docente).delete()
                ProfesorMateriaCurso.objects.get_or_create(partner=docente, materia_curso=materia_curso)
                messages.success(
                    request,
                    f"{docente.nombre} asignado a {materia_curso.grupo} - {materia_curso.materia}.",
                )
            else:
                ProfesorMateriaCurso.objects.filter(materia_curso=materia_curso).delete()
                messages.success(request, f"{materia_curso.grupo} - {materia_curso.materia} quedo sin docente asignado.")

        redirect_url = reverse_lazy("academico:planificacion_docente")
        redirect_params = {"grupo": request.POST.get("grupo") or materia_curso.grupo_id}
        q = request.POST.get("q") or ""
        if q:
            redirect_params["q"] = q
        if redirect_params:
            redirect_url = f"{redirect_url}?{urlencode(redirect_params)}"
        return redirect(redirect_url)

    def get_selected_group(self, cursos):
        grupo_id = self.request.GET.get("grupo") or ""
        if grupo_id:
            selected = next((curso for curso in cursos if str(curso.pk) == str(grupo_id)), None)
            if selected:
                return selected

        pending_group_id = (
            MateriaCurso.objects.filter(grupo__in=cursos, profesor_materia_cursos__isnull=True)
            .order_by("grupo__nombre")
            .values_list("grupo_id", flat=True)
            .first()
        )
        if pending_group_id:
            return next((curso for curso in cursos if curso.pk == pending_group_id), None)
        return cursos[0] if cursos else None

    def get_asignaciones(self):
        today = timezone.localdate()
        return (
            MateriaCurso.objects.select_related("grupo", "materia")
            .prefetch_related(
                Prefetch(
                    "profesor_materia_cursos",
                    queryset=ProfesorMateriaCurso.objects.select_related("partner").order_by("partner__nombre"),
                )
            )
            .annotate(
                total_docentes=Count("profesor_materia_cursos", distinct=True),
                total_clases=Count("clases", distinct=True),
                proximas_clases=Count(
                    "clases",
                    filter=Q(clases__fecha__gte=today, clases__fecha__lte=today + timedelta(days=UNASSIGNED_CLASS_ALERT_DAYS)),
                    distinct=True,
                ),
                proxima_clase=Min("clases__fecha", filter=Q(clases__fecha__gte=today)),
            )
            .order_by("grupo__nombre", "materia__nombre")
        )

    def get_group_tabs(self, cursos, selected_group, q=""):
        rows = (
            MateriaCurso.objects.filter(grupo__in=cursos)
            .values("grupo_id")
            .annotate(
                total=Count("id", distinct=True),
                asignadas=Count("id", filter=Q(profesor_materia_cursos__isnull=False), distinct=True),
            )
        )
        counters = {
            row["grupo_id"]: {
                "total": row["total"],
                "asignadas": row["asignadas"],
                "pendientes": row["total"] - row["asignadas"],
            }
            for row in rows
        }
        tabs = []
        base_url = reverse_lazy("academico:planificacion_docente")
        for curso in cursos:
            params = {"grupo": curso.pk}
            if q:
                params["q"] = q
            stats = counters.get(curso.pk, {"total": 0, "asignadas": 0, "pendientes": 0})
            tabs.append(
                {
                    "grupo": curso,
                    "url": f"{base_url}?{urlencode(params)}",
                    "is_active": bool(selected_group and selected_group.pk == curso.pk),
                    **stats,
                }
            )
        return tabs

    def group_asignaciones(self, asignaciones):
        grupos = []
        grouped = {}
        for materia_curso in asignaciones:
            docentes = [item.partner for item in materia_curso.profesor_materia_cursos.all()]
            item = {
                "materia_curso": materia_curso,
                "docentes": docentes,
                "docente_principal_id": docentes[0].pk if len(docentes) == 1 else "",
                "has_docente": bool(docentes),
                "total_clases": materia_curso.total_clases,
                "proximas_clases": materia_curso.proximas_clases,
                "proxima_clase": materia_curso.proxima_clase,
            }
            grouped.setdefault(materia_curso.grupo, []).append(item)

        for grupo, items in grouped.items():
            pendientes = sum(1 for item in items if not item["has_docente"])
            grupos.append(
                {
                    "grupo": grupo,
                    "items": items,
                    "total": len(items),
                    "pendientes": pendientes,
                    "asignadas": len(items) - pendientes,
                }
            )
        return grupos

    def empty_group_summary(self, selected_group):
        return {
            "grupo": selected_group,
            "items": [],
            "total": 0,
            "pendientes": 0,
            "asignadas": 0,
        }

    def get_stats(self, asignaciones):
        total = len(asignaciones)
        asignadas = sum(1 for item in asignaciones if item.total_docentes)
        return {
            "total": total,
            "asignadas": asignadas,
            "pendientes": total - asignadas,
            "docentes": Partner.objects.filter(es_docente=True, activo=True).count(),
        }


class GrupoEstudianteListView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "academico.view_grupoestudiante"
    template_name = "academico/grupo_estudiantes.html"

    def get(self, request):
        selected_group = self.get_selected_group()
        return render(request, self.template_name, self.get_context(selected_group=selected_group))

    def post(self, request):
        if not self.can_manage(request.user):
            return self.handle_no_permission()

        selected_group = self.get_selected_group()
        action = request.POST.get("assignment_action") or "assign_students"
        if action == "sync_students":
            return self.handle_sync_students(request, selected_group)
        if action == "assign_students":
            return self.handle_assign_students(request, selected_group)
        if action == "move_student":
            return self.handle_move_student(request, selected_group)
        if action == "cancel_move":
            return self.handle_cancel_move(request, selected_group)
        messages.error(request, "Accion no valida.")
        return self.redirect_to_group(selected_group)

    def can_manage(self, user):
        return (
            user.is_superuser
            or user.has_perm("academico.add_grupoestudiante")
            or user.has_perm("academico.change_grupoestudiante")
        )

    def get_selected_group(self):
        grupo_id = self.request.POST.get("grupo") or self.request.GET.get("grupo") or ""
        if grupo_id:
            try:
                return Curso.objects.filter(pk=grupo_id, activo=True).first()
            except (TypeError, ValueError):
                return None
        return Curso.objects.filter(activo=True).order_by("nombre").first()

    def redirect_to_group(self, group=None):
        url = reverse_lazy("academico:grupo_estudiantes")
        if group:
            url = f"{url}?{urlencode({'grupo': group.pk})}"
        return redirect(url)

    def handle_assign_students(self, request, selected_group):
        form = GrupoEstudianteBulkForm(request.POST, selected_group=selected_group)
        if form.is_valid():
            grupo = form.cleaned_data["grupo"]
            saved = 0
            with transaction.atomic():
                for ficha in form.cleaned_data["fichas"]:
                    asignacion = GrupoEstudiante(
                        ficha_inscripcion=ficha,
                        estudiante=ficha.estudiante,
                        grupo=grupo,
                        fecha_asignacion=form.cleaned_data["fecha_asignacion"],
                        estado="activo",
                        usuario_updated=request.user,
                    )
                    asignacion.full_clean()
                    asignacion.save()
                    saved += 1
            if saved:
                messages.success(request, f"{saved} estudiante(s) asignado(s) al grupo.")
            else:
                messages.info(request, "Selecciona al menos un estudiante sin grupo.")
            return self.redirect_to_group(grupo)
        return render(request, self.template_name, self.get_context(selected_group=selected_group, bulk_form=form))

    def handle_sync_students(self, request, selected_group):
        form = GrupoEstudianteBulkForm(request.POST, selected_group=selected_group)
        if form.is_valid():
            grupo = form.cleaned_data["grupo"]
            assignments_to_remove = GrupoEstudiante.objects.filter(
                pk__in=request.POST.getlist("asignaciones_remover"),
                grupo=grupo,
            )
            removed = assignments_to_remove.count()
            saved = 0
            with transaction.atomic():
                assignments_to_remove.delete()
                for ficha in form.cleaned_data["fichas"]:
                    if GrupoEstudiante.objects.filter(ficha_inscripcion=ficha).exists():
                        continue
                    asignacion = GrupoEstudiante(
                        ficha_inscripcion=ficha,
                        estudiante=ficha.estudiante,
                        grupo=grupo,
                        fecha_asignacion=form.cleaned_data["fecha_asignacion"],
                        estado="activo",
                        usuario_updated=request.user,
                    )
                    asignacion.full_clean()
                    asignacion.save()
                    saved += 1
            if saved or removed:
                messages.success(
                    request,
                    f"Grupo actualizado: {saved} asignado(s) a todas sus clases, {removed} removido(s).",
                )
            else:
                messages.info(request, "No hubo cambios para guardar.")
            return self.redirect_to_group(grupo)
        return render(request, self.template_name, self.get_context(selected_group=selected_group, bulk_form=form))

    def handle_move_student(self, request, selected_group):
        form = ClaseEstudianteMovimientoForm(request.POST, grupo=selected_group)
        if form.is_valid():
            asignacion = form.cleaned_data["asignacion"]
            materia_origen = form.cleaned_data["materia_origen"]
            clase_origen = form.cleaned_data["clase_origen"]
            with transaction.atomic():
                active_movement = ClaseEstudianteMovimiento.objects.filter(
                    asignacion=asignacion,
                    clase_origen__materia_curso=materia_origen,
                    activo=True,
                ).first()
                exact_movement = ClaseEstudianteMovimiento.objects.filter(
                    asignacion=asignacion,
                    clase_origen=clase_origen,
                ).first()
                if active_movement and exact_movement and active_movement.pk != exact_movement.pk:
                    active_movement.activo = False
                    active_movement.usuario_updated = request.user
                    active_movement.save(update_fields=["activo", "usuario_updated", "updated_at"])
                movimiento = exact_movement or active_movement or ClaseEstudianteMovimiento(asignacion=asignacion)
                movimiento.asignacion = asignacion
                movimiento.clase_origen = clase_origen
                movimiento.clase_destino = form.cleaned_data["clase_destino"]
                movimiento.fecha_inicio = form.cleaned_data["fecha_inicio"]
                movimiento.motivo = form.cleaned_data.get("motivo") or ""
                movimiento.usuario_updated = request.user
                movimiento.activo = True
                movimiento.full_clean()
                movimiento.save()
            messages.success(
                request,
                "Cambio guardado. El estudiante conserva su grupo base y cursara solo esta materia en el horario destino.",
            )
            return self.redirect_to_group(movimiento.asignacion.grupo)
        return render(request, self.template_name, self.get_context(selected_group=selected_group, movement_form=form))

    def handle_cancel_move(self, request, selected_group):
        movimiento_id = request.POST.get("movimiento_id")
        movimiento = get_object_or_404(
            ClaseEstudianteMovimiento,
            pk=movimiento_id,
            clase_origen__materia_curso__grupo=selected_group,
        )
        movimiento.activo = False
        movimiento.usuario_updated = request.user
        movimiento.save(update_fields=["activo", "usuario_updated", "updated_at"])
        messages.success(request, "Movimiento anulado correctamente.")
        return self.redirect_to_group(selected_group)

    def get_context(self, selected_group=None, bulk_form=None, movement_form=None):
        cursos = list(
            Curso.objects.filter(activo=True)
            .annotate(total_estudiantes=Count(
                "estudiantes_asignados",
                filter=Q(estudiantes_asignados__estado="activo"),
                distinct=True,
            ))
            .order_by("nombre")
        )
        if selected_group is None and cursos:
            selected_group = cursos[0]
        selected_group_id = selected_group.pk if selected_group else None
        q = ""
        asignaciones = GrupoEstudiante.objects.select_related(
            "ficha_inscripcion",
            "estudiante",
            "grupo",
        ).filter(grupo=selected_group) if selected_group else GrupoEstudiante.objects.none()
        asignaciones = asignaciones.order_by("estudiante__nombre")
        bulk_form = bulk_form or GrupoEstudianteBulkForm(selected_group=selected_group)
        clases = list(self.get_group_classes(selected_group))
        movement_materia_cursos = list(self.get_movement_materia_cursos(selected_group))
        movimientos = self.get_group_movements(selected_group)
        return {
            "title": "Estudiantes por grupo",
            "group_tabs": self.get_group_tabs(cursos, selected_group, q),
            "selected_group": selected_group,
            "selected_group_id": selected_group_id,
            "asignaciones": asignaciones,
            "available_fichas": list(bulk_form.fields["fichas"].queryset),
            "clases": clases,
            "movement_materia_cursos": movement_materia_cursos,
            "movimientos": movimientos,
            "bulk_form": bulk_form,
            "movement_form": movement_form or ClaseEstudianteMovimientoForm(grupo=selected_group),
            "movement_materia_map_json": json.dumps(self.get_movement_materia_map(movement_materia_cursos)),
            "can_manage": self.can_manage(self.request.user),
            "q": q,
            "stats": self.get_stats(selected_group),
        }

    def get_group_tabs(self, cursos, selected_group, q=""):
        base_url = reverse_lazy("academico:grupo_estudiantes")
        tabs = []
        for curso in cursos:
            params = {"grupo": curso.pk}
            if q:
                params["q"] = q
            tabs.append(
                {
                    "grupo": curso,
                    "url": f"{base_url}?{urlencode(params)}",
                    "is_active": bool(selected_group and curso.pk == selected_group.pk),
                    "total_estudiantes": curso.total_estudiantes,
                }
            )
        return tabs

    def get_group_classes(self, selected_group):
        if not selected_group:
            return Clase.objects.none()
        return (
            Clase.objects.select_related(
                "materia_curso__materia",
                "materia_curso__grupo",
                "horario_aula_curso__aula_curso__aula",
                "horario_aula_curso__horario_dia__horario",
            )
            .filter(materia_curso__grupo=selected_group)
            .order_by("fecha", "materia_curso__materia__nombre", "horario_aula_curso__horario_dia__horario__hora_inicio")
        )

    def get_movement_materia_cursos(self, selected_group):
        if not selected_group:
            return []
        materias = MateriaCurso.objects.filter(grupo=selected_group).values_list("materia_id", flat=True)
        return (
            MateriaCurso.objects.select_related("materia", "grupo")
            .filter(
                Q(grupo=selected_group) | Q(materia_id__in=materias),
            )
            .filter(clases__isnull=False)
            .distinct()
            .order_by("materia__nombre", "grupo__nombre")
        )

    def get_movement_materia_map(self, materias_curso):
        return {
            str(materia_curso.pk): {
                "materiaId": materia_curso.materia_id,
                "grupoId": materia_curso.grupo_id,
            }
            for materia_curso in materias_curso
        }

    def get_group_movements(self, selected_group):
        if not selected_group:
            return ClaseEstudianteMovimiento.objects.none()
        return (
            ClaseEstudianteMovimiento.objects.select_related(
                "asignacion__estudiante",
                "clase_origen__materia_curso__materia",
                "clase_origen__materia_curso__grupo",
                "clase_origen__horario_aula_curso__aula_curso__aula",
                "clase_origen__horario_aula_curso__horario_dia__horario",
                "clase_destino__materia_curso__grupo",
                "clase_destino__materia_curso__materia",
                "clase_destino__horario_aula_curso__aula_curso__aula",
                "clase_destino__horario_aula_curso__horario_dia__horario",
            )
            .filter(clase_origen__materia_curso__grupo=selected_group)
            .order_by("-fecha_inicio", "-created_at")[:20]
        )

    def get_stats(self, selected_group):
        if not selected_group:
            return {"asignados": 0, "sin_grupo": 0, "clases": 0, "movimientos": 0}
        sin_grupo = (
            FichaInscripcion.objects.filter(estudiante__es_estudiante=True, activo=True)
            .exclude(estado="anulada")
            .filter(asignacion_grupo__isnull=True)
            .count()
        )
        return {
            "asignados": GrupoEstudiante.objects.filter(grupo=selected_group, estado="activo").count(),
            "sin_grupo": sin_grupo,
            "clases": Clase.objects.filter(materia_curso__grupo=selected_group).count(),
            "movimientos": ClaseEstudianteMovimiento.objects.filter(
                clase_origen__materia_curso__grupo=selected_group,
                activo=True,
            ).count(),
        }


class PlanificacionDocenteAsignadorView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "academico.view_profesormateriacurso"
    template_name = "academico/planificacion_docente.html"

    def get(self, request, *args, **kwargs):
        docente = self.get_docente()
        base_form = PlanificacionDocenteBaseForm(initial={"docente": docente})
        formset = self.get_formset(docente=docente)
        return render(request, self.template_name, self.get_context(base_form, formset, docente))

    def post(self, request, *args, **kwargs):
        if not (
            request.user.has_perm("academico.add_profesormateriacurso")
            or request.user.has_perm("academico.change_profesormateriacurso")
            or request.user.is_superuser
        ):
            return self.handle_no_permission()

        base_form = PlanificacionDocenteBaseForm(request.POST)
        docente = None
        if base_form.is_valid():
            docente = base_form.cleaned_data["docente"]
        formset = PlanificacionDocenteFormSet(request.POST, form_kwargs={"docente": docente})

        if base_form.is_valid() and formset.is_valid():
            rows = []
            materia_ids = set()
            duplicate = False
            for form in formset:
                if form.cleaned_data.get("DELETE") or not form.has_assignment_data():
                    continue
                materia_curso = form.cleaned_data["materia_curso"]
                if materia_curso.pk in materia_ids:
                    form.add_error("materia_curso", "Esta materia ya esta repetida en el formulario.")
                    duplicate = True
                    continue
                materia_ids.add(materia_curso.pk)
                rows.append(materia_curso)

            if not duplicate:
                with transaction.atomic():
                    ProfesorMateriaCurso.objects.filter(partner=docente).exclude(materia_curso_id__in=materia_ids).delete()
                    for materia_curso in rows:
                        ProfesorMateriaCurso.objects.get_or_create(partner=docente, materia_curso=materia_curso)
                messages.success(request, "Planificacion docente guardada correctamente.")
                return redirect("academico:planificacion_docente")

        return render(request, self.template_name, self.get_context(base_form, formset, docente))

    def get_docente(self):
        docente_id = self.kwargs.get("docente_pk") or self.request.GET.get("docente")
        if not docente_id:
            return None
        return get_object_or_404(Partner, pk=docente_id, es_docente=True, activo=True)

    def get_formset(self, docente=None):
        initial = []
        if docente:
            initial = [
                {
                    "grupo": item.materia_curso.grupo,
                    "materia_curso": item.materia_curso,
                }
                for item in ProfesorMateriaCurso.objects.select_related(
                    "materia_curso__grupo",
                    "materia_curso__materia",
                )
                .filter(partner=docente)
                .order_by("materia_curso__grupo__nombre", "materia_curso__materia__nombre")
            ]
        if not initial:
            initial = [{}]
        return PlanificacionDocenteFormSet(initial=initial, form_kwargs={"docente": docente})

    def get_context(self, base_form, formset, docente):
        materia_options = [
            {
                "id": item.pk,
                "grupo_id": item.grupo_id,
                "nombre": item.materia.nombre,
            }
            for item in MateriaCurso.objects.select_related("materia", "grupo").order_by("grupo__nombre", "materia__nombre")
        ]
        return {
            "title": "Planificacion docente",
            "base_form": base_form,
            "formset": formset,
            "selected_docente": docente,
            "materia_options_json": json.dumps(materia_options),
            "list_url": reverse_lazy("academico:planificacion_docente"),
            "assign_url": reverse_lazy("academico:planificacion_docente_asignar"),
        }


class CoordinacionPlanificacionListView(CoordinacionRequiredMixin, View):
    template_name = "academico/coordinacion_planificacion_list.html"

    def get(self, request):
        q = request.GET.get("q")
        asignaciones = (
            MateriaCurso.objects.select_related(
                "materia",
                "grupo",
            )
            .prefetch_related(
                Prefetch(
                    "profesor_materia_cursos",
                    queryset=ProfesorMateriaCurso.objects.select_related("partner").order_by("partner__nombre"),
                )
            )
            .annotate(total_temas=Count("planificaciones__temas_planificacion", distinct=True))
            .order_by("grupo__nombre", "materia__nombre")
        )
        if q:
            asignaciones = asignaciones.filter(
                Q(materia__nombre__icontains=q)
                | Q(grupo__nombre__icontains=q)
                | Q(profesor_materia_cursos__partner__nombre__icontains=q)
            )
        return render(
            request,
            self.template_name,
            {
                "title": "Temas y subtemas",
                "asignaciones": asignaciones,
            },
        )


class CoordinacionPlanificacionEditorView(CoordinacionRequiredMixin, View):
    template_name = "academico/coordinacion_planificacion_form.html"

    def get_materia_curso(self):
        pk = self.kwargs.get("materia_curso_pk")
        if pk:
            return get_object_or_404(
                MateriaCurso.objects.select_related("materia", "grupo").prefetch_related(
                    Prefetch(
                        "profesor_materia_cursos",
                        queryset=ProfesorMateriaCurso.objects.select_related("partner").order_by("partner__nombre"),
                    )
                ),
                pk=pk,
            )
        return None

    def get_planificacion(self, materia_curso):
        if not materia_curso:
            return None
        return (
            PlanificacionDocente.objects.filter(materia_curso=materia_curso)
            .order_by("id")
            .first()
        )

    def ensure_planificacion(self, materia_curso):
        nombre = f"{materia_curso.grupo} - {materia_curso.materia}"
        planificacion, _ = PlanificacionDocente.objects.get_or_create(
            materia_curso=materia_curso,
            defaults={"nombre": nombre},
        )
        return planificacion

    def get(self, request, *args, **kwargs):
        materia_curso = self.get_materia_curso()
        planificacion = self.get_planificacion(materia_curso)
        form = CoordinacionPlanificacionForm(materia_curso=materia_curso)
        formset = CoordinacionTemaFormSet(initial=self.get_tema_initial(planificacion))
        return render(request, self.template_name, self.get_context(form, formset, materia_curso, planificacion))

    def post(self, request, *args, **kwargs):
        materia_curso = self.get_materia_curso()
        form = CoordinacionPlanificacionForm(request.POST, materia_curso=materia_curso)
        formset = CoordinacionTemaFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                materia_curso = materia_curso or form.cleaned_data["materia_curso"]
                planificacion = self.ensure_planificacion(materia_curso)
                kept_tema_ids = set()
                for tema_index, tema_form in enumerate(formset):
                    if tema_form.cleaned_data.get("DELETE") or not tema_form.has_topic_data():
                        continue
                    tema_id = tema_form.cleaned_data.get("tema_id")
                    tema = None
                    if tema_id:
                        tema = planificacion.temas_planificacion.filter(pk=tema_id).first()
                    if tema is None:
                        tema = Tema(planificacion=planificacion)
                    tema.nombre = tema_form.cleaned_data["nombre"]
                    tema.detalle = tema_form.cleaned_data.get("detalle") or None
                    tema.orden = len(kept_tema_ids) + 1
                    tema.save()
                    kept_tema_ids.add(tema.pk)

                    submitted_subtemas = self.get_subtemas_from_post(tema_index)
                    kept_subtema_ids = set()
                    for subtema_order, subtema_data in enumerate(submitted_subtemas, start=1):
                        subtema = None
                        if subtema_data["id"]:
                            subtema = tema.subtemas_planificacion.filter(pk=subtema_data["id"]).first()
                        if subtema_data["delete"] or not subtema_data["nombre"]:
                            if subtema:
                                subtema.delete()
                            continue
                        if subtema:
                            subtema.nombre = subtema_data["nombre"]
                            subtema.descripcion = None
                            subtema.orden = subtema_order
                            subtema.save(update_fields=["nombre", "descripcion", "orden"])
                        else:
                            subtema = tema.subtemas_planificacion.create(
                                nombre=subtema_data["nombre"],
                                orden=subtema_order,
                            )
                        kept_subtema_ids.add(subtema.pk)
                    tema.subtemas_planificacion.exclude(pk__in=kept_subtema_ids).delete()

                planificacion.temas_planificacion.exclude(pk__in=kept_tema_ids).delete()
            messages.success(request, "Temas y subtemas guardados correctamente.")
            return redirect("academico:coordinacion_planificacion_editar", materia_curso_pk=materia_curso.pk)
        return render(request, self.template_name, self.get_context(form, formset, materia_curso, self.get_planificacion(materia_curso)))

    def get_subtemas_from_post(self, tema_index):
        prefix = f"form-{tema_index}-subtemas"
        try:
            total = int(self.request.POST.get(f"{prefix}-TOTAL_FORMS", 0))
        except (TypeError, ValueError):
            total = 0
        subtemas = []
        for index in range(total):
            row_prefix = f"{prefix}-{index}"
            subtemas.append(
                {
                    "id": self.request.POST.get(f"{row_prefix}-id") or "",
                    "nombre": (self.request.POST.get(f"{row_prefix}-nombre") or "").strip(),
                    "delete": self.request.POST.get(f"{row_prefix}-DELETE") == "on",
                }
            )
        return subtemas

    def get_tema_initial(self, planificacion):
        if not planificacion:
            return [{}]
        initial = []
        temas = planificacion.temas_planificacion.prefetch_related("subtemas_planificacion").order_by("orden", "nombre")
        for tema in temas:
            initial.append(
                {
                    "tema_id": tema.pk,
                    "nombre": tema.nombre,
                    "detalle": tema.detalle,
                    "orden": tema.orden,
                    "subtemas": [
                        {"id": subtema.pk, "nombre": subtema.nombre}
                        for subtema in tema.subtemas_planificacion.order_by("orden", "nombre")
                    ],
                }
            )
        return initial or [{}]

    def get_context(self, form, formset, materia_curso, planificacion):
        docentes = []
        if materia_curso:
            docentes = [
                item.partner
                for item in materia_curso.profesor_materia_cursos.all()
            ]
        materia_docentes = {}
        for item in MateriaCurso.objects.prefetch_related(
            Prefetch(
                "profesor_materia_cursos",
                queryset=ProfesorMateriaCurso.objects.select_related("partner").order_by("partner__nombre"),
            )
        ):
            materia_docentes[str(item.pk)] = [
                asignacion.partner.nombre
                for asignacion in item.profesor_materia_cursos.all()
            ]
        return {
            "title": "Temas y subtemas",
            "form": form,
            "formset": formset,
            "materia_curso": materia_curso,
            "docentes": docentes,
            "planificacion": planificacion,
            "materia_docentes_json": json.dumps(materia_docentes),
            "tema_suggestions": Tema.objects.order_by("nombre").values_list("nombre", flat=True).distinct(),
            "list_url": reverse_lazy("academico:coordinacion_planificacion_list"),
        }


class DocenteHorariosView(LoginRequiredMixin, View):
    template_name = "academico/docente_horarios.html"
    status_filters = (
        {
            "key": "trabajo",
            "label": "Por atender",
            "states": ("pendiente", "rechazada"),
            "icon": "ri-inbox-unarchive-line",
        },
        {
            "key": "revision",
            "label": "En revision",
            "states": ("revision",),
            "icon": "ri-search-eye-line",
        },
        {
            "key": "rechazada",
            "label": "Observadas",
            "states": ("rechazada",),
            "icon": "ri-error-warning-line",
        },
        {
            "key": "aprobada",
            "label": "Aprobadas",
            "states": ("aprobada",),
            "icon": "ri-checkbox-circle-line",
        },
        {
            "key": "todas",
            "label": "Todas",
            "states": None,
            "icon": "ri-calendar-check-line",
        },
    )

    def get(self, request):
        docente = getattr(request.user, "partner", None)
        if not docente or not docente.es_docente:
            return render(
                request,
                self.template_name,
                {
                    "title": "Mis planificaciones",
                    "docente": None,
                    "calendar_events_json": json.dumps([]),
                    "calendar_default_date": timezone.localdate().isoformat(),
                    "has_events": False,
                    "planificacion_stats": self.empty_stats(),
                    "status_tabs": [],
                    "selected_filter": "trabajo",
                    "selected_filter_label": "",
                    "planificacion_cards": [],
                },
            )

        clases = list(
            Clase.objects.select_related(
                "materia_curso__materia",
                "materia_curso__grupo",
                "docente",
                "horario_aula_curso__aula_curso__aula",
                "horario_aula_curso__aula_curso__curso",
                "horario_aula_curso__horario_dia__horario",
            )
            .prefetch_related("competencias", "estrategias", "recursos")
            .filter(docente_responsable_filter(docente))
            .distinct()
            .order_by("fecha", "horario_aula_curso__horario_dia__horario__hora_inicio")
        )
        stats = self.get_planificacion_stats(clases)
        selected_filter = self.get_selected_filter(request.GET.get("estado"), stats)
        status_tabs = self.get_status_tabs(selected_filter, stats)
        planificacion_cards = [
            self.build_planificacion_card(clase)
            for clase in self.filter_clases(clases, selected_filter)
        ]
        calendar_events = []
        calendar_default_date = timezone.localdate().isoformat()
        first_clase = clases[0] if clases else None
        if first_clase:
            calendar_default_date = first_clase.fecha.isoformat()

        for clase in clases:
            horario = clase.horario_aula_curso.horario_dia.horario
            materia = clase.materia_curso.materia
            aula = clase.horario_aula_curso.aula_curso.aula
            grupo = clase.materia_curso.grupo
            event_color = materia.color
            calendar_events.append(
                {
                    "id": clase.pk,
                    "title": f"{grupo.nombre} · {aula} · {materia.nombre}",
                    "start": f"{clase.fecha.isoformat()}T{horario.hora_inicio:%H:%M:%S}",
                    "end": f"{clase.fecha.isoformat()}T{horario.hora_fin:%H:%M:%S}",
                    "allDay": False,
                    "className": f"materia-event docente-event estado-{clase.estado_planificacion}",
                    "backgroundColor": event_color,
                    "borderColor": event_color,
                    "textColor": readable_text_color(event_color),
                    "grupo": grupo.nombre,
                    "aula": str(aula),
                    "materia": materia.nombre,
                    "hora": f"{horario.hora_inicio:%H:%M} - {horario.hora_fin:%H:%M}",
                    "estado": clase.get_estado_planificacion_display(),
                    "url": str(reverse_lazy("academico:docente_clase_planificar", kwargs={"pk": clase.pk})),
                }
            )

        return render(
            request,
            self.template_name,
            {
                "title": "Mis planificaciones",
                "docente": docente,
                "calendar_events_json": json.dumps(calendar_events),
                "calendar_default_date": calendar_default_date,
                "has_events": bool(calendar_events),
                "planificacion_stats": stats,
                "status_tabs": status_tabs,
                "selected_filter": selected_filter,
                "selected_filter_label": self.get_filter_label(selected_filter),
                "planificacion_cards": planificacion_cards,
            },
        )

    def empty_stats(self):
        return {
            "total": 0,
            "pendiente": 0,
            "revision": 0,
            "rechazada": 0,
            "aprobada": 0,
            "por_atender": 0,
            "avance": 0,
        }

    def get_planificacion_stats(self, clases):
        stats = self.empty_stats()
        stats["total"] = len(clases)
        for clase in clases:
            if clase.estado_planificacion in stats:
                stats[clase.estado_planificacion] += 1
        stats["por_atender"] = stats["pendiente"] + stats["rechazada"]
        stats["avance"] = round((stats["aprobada"] / stats["total"]) * 100) if stats["total"] else 0
        return stats

    def get_selected_filter(self, requested_filter, stats):
        valid_filters = {item["key"] for item in self.status_filters}
        if requested_filter in valid_filters:
            return requested_filter
        if stats["por_atender"]:
            return "trabajo"
        if stats["revision"]:
            return "revision"
        return "todas"

    def get_filter_label(self, selected_filter):
        filter_item = next((item for item in self.status_filters if item["key"] == selected_filter), None)
        return filter_item["label"] if filter_item else ""

    def get_status_tabs(self, selected_filter, stats):
        base_url = reverse_lazy("academico:docente_horarios")
        tabs = []
        for item in self.status_filters:
            count = stats["total"] if item["states"] is None else sum(stats[state] for state in item["states"])
            tabs.append(
                {
                    **item,
                    "count": count,
                    "url": f"{base_url}?{urlencode({'estado': item['key']})}",
                    "is_active": item["key"] == selected_filter,
                }
            )
        return tabs

    def filter_clases(self, clases, selected_filter):
        filter_item = next((item for item in self.status_filters if item["key"] == selected_filter), None)
        if not filter_item or filter_item["states"] is None:
            return clases
        allowed_states = set(filter_item["states"])
        return [clase for clase in clases if clase.estado_planificacion in allowed_states]

    def build_planificacion_card(self, clase):
        horario = clase.horario_aula_curso.horario_dia.horario
        competencias = list(clase.competencias.all())
        estrategias = list(clase.estrategias.all())
        recursos = list(clase.recursos.all())
        observaciones = clase.observaciones_revision or {}
        steps = [
            {"label": "Tema", "done": bool(clase.tema_id), "note": observaciones.get("tema", "")},
            {"label": "Detalle", "done": bool(clase.descripcion), "note": observaciones.get("detalle", "")},
            {"label": "Competencias", "done": bool(competencias), "note": observaciones.get("competencias", "")},
            {"label": "Estrategias", "done": bool(estrategias), "note": observaciones.get("estrategias", "")},
            {"label": "Recursos", "done": bool(recursos), "note": observaciones.get("recursos", "")},
        ]
        completed_steps = sum(1 for item in steps if item["done"])
        action_labels = {
            "pendiente": "Planificar",
            "revision": "Ver envio",
            "rechazada": "Corregir",
            "aprobada": "Ver",
        }
        return {
            "clase": clase,
            "horario": horario,
            "estado": clase.estado_planificacion,
            "estado_label": clase.get_estado_planificacion_display(),
            "aula": clase.horario_aula_curso.aula_curso.aula,
            "grupo": clase.materia_curso.grupo,
            "materia": clase.materia_curso.materia,
            "tema": clase.tema,
            "subtema": clase.subtema,
            "steps": steps,
            "completed_steps": completed_steps,
            "progress": round((completed_steps / len(steps)) * 100),
            "revision_note": clase.notas_revision if clase.estado_planificacion == "rechazada" else "",
            "is_late": clase.fecha < timezone.localdate() and clase.estado_planificacion in {"pendiente", "rechazada"},
            "action_label": action_labels.get(clase.estado_planificacion, "Abrir"),
            "url": reverse_lazy("academico:docente_clase_planificar", kwargs={"pk": clase.pk}),
            "can_take_attendance": clase.fecha == timezone.localdate() and not clase.asistencia_cerrada,
            "attendance_closed": clase.asistencia_cerrada,
            "attendance_url": reverse_lazy("academico:docente_clase_asistencia", kwargs={"pk": clase.pk}),
        }


class DocenteCalendarioMixin:
    weekday_headers = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]

    def get_docente(self):
        docente = getattr(self.request.user, "partner", None)
        if docente and docente.es_docente:
            return docente
        return None

    def get_selected_date(self):
        selected = (self.request.GET.get("fecha") or "").strip()
        if selected:
            try:
                return date.fromisoformat(selected)
            except ValueError:
                pass
        return timezone.localdate()

    def get_week_bounds(self, selected_date):
        week_start = selected_date - timedelta(days=selected_date.weekday())
        return week_start, week_start + timedelta(days=6)

    def get_docente_clases_queryset(self, docente):
        return (
            Clase.objects.select_related(
                "materia_curso__materia",
                "materia_curso__grupo",
                "docente",
                "tema",
                "subtema",
                "horario_aula_curso__aula_curso__aula",
                "horario_aula_curso__horario_dia__dia",
                "horario_aula_curso__horario_dia__horario",
            )
            .filter(docente_responsable_filter(docente))
            .distinct()
            .order_by(
                "fecha",
                "horario_aula_curso__horario_dia__horario__hora_inicio",
                "materia_curso__grupo__nombre",
                "materia_curso__materia__nombre",
            )
        )

    def build_schedule_row(self, clase):
        horario = clase.horario_aula_curso.horario_dia.horario
        materia = clase.materia_curso.materia
        grupo = clase.materia_curso.grupo
        aula = clase.horario_aula_curso.aula_curso.aula
        return {
            "clase": clase,
            "fecha": clase.fecha,
            "weekday": clase.fecha.weekday(),
            "time_key": (horario.hora_inicio, horario.hora_fin),
            "hora": f"{horario.hora_inicio:%H:%M} - {horario.hora_fin:%H:%M}",
            "materia": materia.nombre,
            "materia_corta": materia.nombre_corto or materia.nombre,
            "grupo": grupo.nombre,
            "aula": str(aula),
            "tema": str(clase.tema) if clase.tema else "",
            "subtema": str(clase.subtema) if clase.subtema else "",
            "estado": clase.get_estado_planificacion_display(),
            "color": materia.color,
            "url": str(reverse_lazy("academico:docente_clase_planificar", kwargs={"pk": clase.pk})),
        }

    def build_calendar_event(self, clase):
        row = self.build_schedule_row(clase)
        start_time, end_time = row["time_key"]
        event_color = row["color"]
        title = f"{row['materia_corta']} · {row['grupo']}"
        return {
            "id": clase.pk,
            "title": title,
            "start": f"{row['fecha'].isoformat()}T{start_time:%H:%M:%S}",
            "end": f"{row['fecha'].isoformat()}T{end_time:%H:%M:%S}",
            "allDay": False,
            "className": f"materia-event docente-schedule-event estado-{clase.estado_planificacion}",
            "backgroundColor": event_color,
            "borderColor": event_color,
            "textColor": readable_text_color(event_color),
            "materia": row["materia"],
            "grupo": row["grupo"],
            "aula": row["aula"],
            "hora": row["hora"],
            "tema": row["tema"],
            "subtema": row["subtema"],
            "estado": row["estado"],
            "url": row["url"],
        }


class DocenteCalendarioView(LoginRequiredMixin, DocenteCalendarioMixin, View):
    template_name = "academico/docente_calendario.html"

    def get(self, request):
        docente = self.get_docente()
        selected_date = self.get_selected_date()
        week_start, week_end = self.get_week_bounds(selected_date)
        export_base_url = reverse_lazy("academico:docente_calendario_exportar")
        export_url = f"{export_base_url}?{urlencode({'fecha': selected_date.isoformat()})}"
        context = {
            "title": "Mi calendario",
            "docente": docente,
            "selected_date": selected_date,
            "week_start": week_start,
            "week_end": week_end,
            "calendar_events_json": json.dumps([]),
            "calendar_default_date": selected_date.isoformat(),
            "has_events": False,
            "week_count": 0,
            "total_count": 0,
            "materia_count": 0,
            "grupo_count": 0,
            "export_base_url": export_base_url,
            "export_url": export_url,
        }
        if not docente:
            return render(request, self.template_name, context)

        clases = list(self.get_docente_clases_queryset(docente))
        week_rows = [self.build_schedule_row(clase) for clase in clases if week_start <= clase.fecha <= week_end]
        context.update(
            {
                "calendar_events_json": json.dumps([self.build_calendar_event(clase) for clase in clases]),
                "has_events": bool(clases),
                "week_count": len(week_rows),
                "total_count": len(clases),
                "materia_count": len({row["materia"] for row in week_rows}),
                "grupo_count": len({row["grupo"] for row in week_rows}),
            }
        )
        return render(request, self.template_name, context)


class DocenteCalendarioExportView(LoginRequiredMixin, DocenteCalendarioMixin, View):
    def get(self, request):
        docente = self.get_docente()
        if not docente:
            return HttpResponse("Tu usuario no esta vinculado a un docente activo.", status=403)

        selected_date = self.get_selected_date()
        week_start, week_end = self.get_week_bounds(selected_date)
        rows = [
            self.build_schedule_row(clase)
            for clase in self.get_docente_clases_queryset(docente).filter(fecha__range=(week_start, week_end))
        ]
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = safe_sheet_title("Mi horario")
        self.write_week_sheet(sheet, docente, week_start, week_end, rows)

        output = BytesIO()
        workbook.save(output)
        output.seek(0)
        filename = f"mi_horario_{week_start:%Y%m%d}.xlsx"
        response = HttpResponse(
            output.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    def write_week_sheet(self, sheet, docente, week_start, week_end, rows):
        title_fill = PatternFill("solid", fgColor="DCEBFF")
        header_fill = PatternFill("solid", fgColor="0F766E")
        time_fill = PatternFill("solid", fgColor="134E4A")
        empty_fill = PatternFill("solid", fgColor="FFFFFF")
        thin = Side(style="thin", color="D7DEE8")
        border = Border(left=thin, right=thin, top=thin, bottom=thin)
        center = Alignment(horizontal="center", vertical="center", wrap_text=True)
        schedule_alignment = Alignment(horizontal="center", vertical="top", wrap_text=True)

        sheet.merge_cells(start_row=1, start_column=1, end_row=1, end_column=8)
        title_cell = sheet.cell(row=1, column=1, value=f"Horario semanal - {docente.nombre}")
        title_cell.font = Font(bold=True, size=14, color="111827")
        title_cell.fill = title_fill
        title_cell.alignment = center

        sheet.merge_cells(start_row=2, start_column=1, end_row=2, end_column=8)
        week_cell = sheet.cell(row=2, column=1, value=f"Semana {week_start:%d/%m/%Y} - {week_end:%d/%m/%Y}")
        week_cell.font = Font(bold=True, color="111827")
        week_cell.fill = title_fill
        week_cell.alignment = center

        sheet.cell(row=4, column=1, value="Hora")
        for col, day in enumerate(self.weekday_headers, start=2):
            day_date = week_start + timedelta(days=col - 2)
            sheet.cell(row=4, column=col, value=f"{day}\n{day_date:%d/%m}")
        for col in range(1, 9):
            cell = sheet.cell(row=4, column=col)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = header_fill
            cell.border = border
            cell.alignment = center

        time_slots = sorted({row["time_key"] for row in rows})
        week_matrix = {}
        for row in rows:
            week_matrix.setdefault((row["time_key"], row["weekday"]), []).append(row)

        current_row = 5
        if not time_slots:
            sheet.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=8)
            cell = sheet.cell(row=current_row, column=1, value="Sin clases asignadas en esta semana.")
            cell.alignment = center
            cell.border = border
        for time_slot in time_slots:
            start_time, end_time = time_slot
            time_cell = sheet.cell(row=current_row, column=1, value=f"{start_time:%H:%M} - {end_time:%H:%M}")
            time_cell.font = Font(bold=True, color="FFFFFF")
            time_cell.fill = time_fill
            time_cell.border = border
            time_cell.alignment = center
            max_lines = 1
            for weekday in range(7):
                cell = sheet.cell(row=current_row, column=weekday + 2)
                entries = week_matrix.get((time_slot, weekday), [])
                if entries:
                    cell.value = "\n\n".join(self.schedule_label(row) for row in entries)
                    cell.fill = PatternFill("solid", fgColor=xlsx_color(entries[0]["color"]))
                    cell.font = Font(color=xlsx_color(readable_text_color(entries[0]["color"])), bold=True, size=9)
                    max_lines = max(max_lines, estimated_schedule_wrapped_lines(cell.value))
                else:
                    cell.value = ""
                    cell.fill = empty_fill
                cell.border = border
                cell.alignment = schedule_alignment
            sheet.row_dimensions[current_row].height = schedule_export_row_height(max_lines)
            current_row += 1

        widths = [18] + [SCHEDULE_EXPORT_COLUMN_WIDTH] * 7
        for col, width in enumerate(widths, start=1):
            sheet.column_dimensions[get_column_letter(col)].width = width
        sheet.freeze_panes = "B5"

    def schedule_label(self, row):
        parts = [row["materia"], row["grupo"], row["aula"]]
        if row["tema"]:
            parts.append(row["tema"])
        if row["subtema"]:
            parts.append(row["subtema"])
        return "\n".join(parts)


class DocenteClaseAsistenciaView(LoginRequiredMixin, View):
    template_name = "academico/docente_clase_asistencia.html"

    def get_docente(self):
        docente = getattr(self.request.user, "partner", None)
        if docente and docente.es_docente:
            return docente
        return None

    def get_clase(self):
        docente = self.get_docente()
        if not docente:
            return get_object_or_404(Clase.objects.none(), pk=self.kwargs["pk"])
        return get_object_or_404(
            Clase.objects.select_related(
                "materia_curso__materia",
                "materia_curso__grupo",
                "docente",
                "horario_aula_curso__aula_curso__aula",
                "horario_aula_curso__horario_dia__horario",
            )
            .filter(docente_responsable_filter(docente))
            .distinct(),
            pk=self.kwargs["pk"],
        )

    def get(self, request, pk):
        clase = self.get_clase()
        date_response = self.ensure_attendance_date(request, clase)
        if date_response:
            return date_response
        return render(request, self.template_name, self.get_context(clase))

    def post(self, request, pk):
        clase = self.get_clase()
        date_response = self.ensure_attendance_date(request, clase)
        if date_response:
            return date_response
        action = request.POST.get("attendance_action") or "save"
        if action == "close":
            return self.handle_close(request, clase)
        if action != "save":
            messages.error(request, "Accion no valida.")
            return redirect("academico:docente_clase_asistencia", pk=clase.pk)
        if clase.asistencia_cerrada:
            messages.error(request, "La asistencia ya esta cerrada y no se puede modificar.")
            return redirect("academico:docente_clase_asistencia", pk=clase.pk)
        rows, moved_out_rows = self.get_roster_rows(clase)
        valid_states = {choice[0] for choice in ClaseAsistencia.ESTADO_CHOICES}
        registrado_por = self.get_docente()
        with transaction.atomic():
            if moved_out_rows:
                ClaseAsistencia.objects.filter(
                    clase=clase,
                    estudiante_id__in=[row["asignacion"].estudiante_id for row in moved_out_rows],
                ).delete()
            for row in rows:
                asignacion = row["asignacion"]
                estado = request.POST.get(f"estado_{asignacion.pk}", "presente")
                if estado not in valid_states:
                    estado = "presente"
                observacion = (request.POST.get(f"observacion_{asignacion.pk}") or "").strip()
                ClaseAsistencia.objects.update_or_create(
                    clase=clase,
                    estudiante=asignacion.estudiante,
                    defaults={
                        "estado": estado,
                        "observacion": observacion,
                        "registrado_por": registrado_por,
                        "usuario_updated": request.user,
                    },
                )
        messages.success(request, f"Asistencia guardada para {len(rows)} estudiante(s).")
        return redirect("academico:docente_clase_asistencia", pk=clase.pk)

    def ensure_attendance_date(self, request, clase):
        if clase.fecha == timezone.localdate():
            return None
        messages.error(request, "La asistencia solo se habilita el dia de la clase.")
        return redirect("academico:docente_horarios")

    def handle_close(self, request, clase):
        if clase.asistencia_cerrada:
            messages.info(request, "La asistencia ya estaba cerrada.")
            return redirect("academico:docente_clase_asistencia", pk=clase.pk)
        rows, _ = self.get_roster_rows(clase)
        if not rows:
            messages.error(request, "No hay estudiantes para cerrar la asistencia.")
            return redirect("academico:docente_clase_asistencia", pk=clase.pk)
        saved_student_ids = set(ClaseAsistencia.objects.filter(clase=clase).values_list("estudiante_id", flat=True))
        pending_rows = [row for row in rows if row["asignacion"].estudiante_id not in saved_student_ids]
        if pending_rows:
            messages.error(request, "Guarda la asistencia antes de cerrarla.")
            return redirect("academico:docente_clase_asistencia", pk=clase.pk)
        clase.asistencia_cerrada = True
        clase.asistencia_cerrada_por = self.get_docente()
        clase.fecha_cierre_asistencia = timezone.now()
        clase.save(update_fields=["asistencia_cerrada", "asistencia_cerrada_por", "fecha_cierre_asistencia"])
        messages.success(request, "Asistencia cerrada correctamente.")
        return redirect("academico:docente_clase_asistencia", pk=clase.pk)

    def get_context(self, clase):
        rows, moved_out_rows = self.get_roster_rows(clase)
        horario = clase.horario_aula_curso.horario_dia.horario
        has_saved_attendance = ClaseAsistencia.objects.filter(clase=clase).exists()
        can_edit_attendance = clase.fecha == timezone.localdate() and not clase.asistencia_cerrada
        return {
            "title": "Asistencia",
            "clase": clase,
            "horario": horario,
            "rows": rows,
            "moved_out_rows": moved_out_rows,
            "estado_choices": ClaseAsistencia.ESTADO_CHOICES,
            "total_estudiantes": len(rows),
            "can_edit_attendance": can_edit_attendance,
            "can_close_attendance": can_edit_attendance and bool(rows) and has_saved_attendance,
            "has_saved_attendance": has_saved_attendance,
            "planificacion_url": reverse_lazy("academico:docente_clase_planificar", kwargs={"pk": clase.pk}),
            "cancel_url": reverse_lazy("academico:docente_horarios"),
        }

    def get_roster_rows(self, clase):
        base_asignaciones = list(
            GrupoEstudiante.objects.select_related("estudiante", "ficha_inscripcion", "grupo")
            .filter(grupo=clase.materia_curso.grupo, estado="activo")
            .order_by("estudiante__nombre", "ficha_inscripcion__numero")
        )
        movimientos = list(
            ClaseEstudianteMovimiento.objects.select_related(
                "asignacion__estudiante",
                "asignacion__ficha_inscripcion",
                "asignacion__grupo",
                "clase_origen__materia_curso__materia",
                "clase_origen__materia_curso__grupo",
                "clase_origen__horario_aula_curso__aula_curso__aula",
                "clase_origen__horario_aula_curso__horario_dia__horario",
                "clase_destino__materia_curso__materia",
                "clase_destino__materia_curso__grupo",
                "clase_destino__horario_aula_curso__aula_curso__aula",
                "clase_destino__horario_aula_curso__horario_dia__horario",
            )
            .filter(
                activo=True,
                fecha_inicio__lte=clase.fecha,
            )
            .filter(
                Q(clase_origen__materia_curso=clase.materia_curso)
                | Q(clase_destino__materia_curso=clase.materia_curso)
            )
        )
        moved_out_by_assignment = {
            movimiento.asignacion_id: movimiento
            for movimiento in movimientos
            if movimiento.clase_origen.materia_curso_id == clase.materia_curso_id
        }
        incoming_by_assignment = {
            movimiento.asignacion_id: movimiento
            for movimiento in movimientos
            if movimiento.clase_destino.materia_curso_id == clase.materia_curso_id
        }
        visible_assignments_by_id = {
            asignacion.pk: asignacion
            for asignacion in base_asignaciones
            if asignacion.pk not in moved_out_by_assignment
        }
        visible_assignments_by_id.update(
            {
                movimiento.asignacion_id: movimiento.asignacion
                for movimiento in incoming_by_assignment.values()
            }
        )
        visible_assignments = sorted(
            visible_assignments_by_id.values(),
            key=lambda asignacion: (
                asignacion.estudiante.nombre or "",
                asignacion.ficha_inscripcion.numero or "",
            ),
        )
        attendance_by_student = {
            attendance.estudiante_id: attendance
            for attendance in ClaseAsistencia.objects.filter(
                clase=clase,
                estudiante_id__in=[asignacion.estudiante_id for asignacion in visible_assignments],
            )
        }
        rows = []
        for asignacion in visible_assignments:
            attendance = attendance_by_student.get(asignacion.estudiante_id)
            rows.append(
                {
                    "asignacion": asignacion,
                    "estudiante": asignacion.estudiante,
                    "ficha": asignacion.ficha_inscripcion,
                    "attendance": attendance,
                    "estado": attendance.estado if attendance else "presente",
                    "observacion": attendance.observacion if attendance else "",
                    "incoming": incoming_by_assignment.get(asignacion.pk),
                }
            )
        moved_out_rows = [
            {
                "movimiento": movimiento,
                "asignacion": movimiento.asignacion,
                "estudiante": movimiento.asignacion.estudiante,
                "destino_label": self.clase_label(movimiento.clase_destino),
            }
            for movimiento in moved_out_by_assignment.values()
        ]
        return rows, sorted(moved_out_rows, key=lambda row: row["estudiante"].nombre)

    @staticmethod
    def clase_label(clase):
        horario = clase.horario_aula_curso.horario_dia.horario
        return (
            f"{clase.fecha:%d/%m/%Y} - "
            f"{clase.horario_aula_curso.aula_curso.aula} - "
            f"{horario.hora_inicio:%H:%M}-{horario.hora_fin:%H:%M}"
        )


class CoordinacionRevisionAsistenciaView(CoordinacionRequiredMixin, View):
    template_name = "academico/coordinacion_revision_asistencia.html"
    status_filters = (
        {"key": "todas", "label": "Todas", "icon": "ri-list-check-3"},
        {"key": "pendientes", "label": "Pendientes", "icon": "ri-time-line"},
        {"key": "ausentes", "label": "Con ausentes", "icon": "ri-user-unfollow-line"},
        {"key": "observaciones", "label": "Observaciones", "icon": "ri-chat-3-line"},
        {"key": "cerradas", "label": "Cerradas", "icon": "ri-lock-2-line"},
    )
    attendance_state_labels = {**dict(ClaseAsistencia.ESTADO_CHOICES), "pendiente": "Pendiente"}

    def get(self, request):
        selected_grupo = self.get_selected_grupo()
        selected_docente = self.get_selected_docente()
        requested_estado = request.GET.get("estado", "")
        clases_queryset = self.get_clases_queryset()

        if selected_grupo:
            clases_queryset = clases_queryset.filter(materia_curso__grupo=selected_grupo)
        if selected_docente:
            clases_queryset = clases_queryset.filter(docente_responsable_filter(selected_docente))

        cards = [self.build_attendance_card(clase) for clase in clases_queryset.distinct()]
        stats = self.get_attendance_stats(cards)
        selected_estado = self.get_selected_filter(requested_estado)
        attendance_cards = self.filter_cards(cards, selected_estado)
        return render(
            request,
            self.template_name,
            {
                "title": "Revision de asistencia",
                "attendance_cards": attendance_cards,
                "attendance_stats": stats,
                "grupos": Curso.objects.filter(activo=True).order_by("nombre"),
                "docentes": Partner.objects.filter(es_docente=True, activo=True).order_by("nombre"),
                "selected_grupo": selected_grupo,
                "selected_grupo_id": str(selected_grupo.pk) if selected_grupo else "",
                "selected_docente": selected_docente,
                "selected_docente_id": str(selected_docente.pk) if selected_docente else "",
                "selected_estado": selected_estado,
                "selected_estado_label": self.get_filter_label(selected_estado),
                "status_tabs": self.get_status_tabs(selected_estado, selected_grupo, selected_docente, stats),
            },
        )

    def get_clases_queryset(self):
        return (
            Clase.objects.select_related(
                "materia_curso__materia",
                "materia_curso__grupo",
                "docente",
                "asistencia_cerrada_por",
                "horario_aula_curso__aula_curso__aula",
                "horario_aula_curso__horario_dia__horario",
            )
            .prefetch_related("materia_curso__profesor_materia_cursos__partner")
            .order_by("fecha", "horario_aula_curso__horario_dia__horario__hora_inicio", "materia_curso__grupo__nombre")
        )

    def get_selected_grupo(self):
        grupo_id = self.request.GET.get("grupo") or ""
        if not grupo_id:
            return None
        try:
            return Curso.objects.filter(pk=grupo_id, activo=True).first()
        except (TypeError, ValueError):
            return None

    def get_selected_docente(self):
        docente_id = self.request.GET.get("docente") or ""
        if not docente_id:
            return None
        try:
            return Partner.objects.filter(pk=docente_id, es_docente=True, activo=True).first()
        except (TypeError, ValueError):
            return None

    def build_attendance_card(self, clase):
        rows, moved_out_rows = DocenteClaseAsistenciaView().get_roster_rows(clase)
        horario = clase.horario_aula_curso.horario_dia.horario
        counts = {key: 0 for key, _ in ClaseAsistencia.ESTADO_CHOICES}
        counts["pendiente"] = 0
        fichas = []
        observation_rows = []
        for row in rows:
            attendance = row["attendance"]
            estado = attendance.estado if attendance else "pendiente"
            counts[estado] = counts.get(estado, 0) + 1
            observacion = row["observacion"] or ""
            ficha_row = {
                "ficha": row["ficha"],
                "estudiante": row["estudiante"],
                "estado": estado,
                "estado_label": self.attendance_state_labels.get(estado, estado),
                "observacion": observacion,
                "incoming": row["incoming"],
            }
            fichas.append(ficha_row)
            if observacion:
                observation_rows.append(ficha_row)

        pending_count = counts.get("pendiente", 0)
        saved_count = len(rows) - pending_count
        status_key, status_label = self.get_card_status(clase, len(rows), pending_count)
        return {
            "clase": clase,
            "horario": horario,
            "grupo": clase.materia_curso.grupo,
            "materia": clase.materia_curso.materia,
            "aula": clase.horario_aula_curso.aula_curso.aula,
            "docentes": get_clase_docentes(clase),
            "counts": counts,
            "count_items": self.get_count_items(counts),
            "fichas": fichas,
            "moved_out_rows": moved_out_rows,
            "observation_rows": observation_rows,
            "observation_count": len(observation_rows),
            "total_estudiantes": len(rows),
            "saved_count": saved_count,
            "pending_count": pending_count,
            "status_key": status_key,
            "status_label": status_label,
            "is_today": clase.fecha == timezone.localdate(),
            "report_url": reverse_lazy("academico:coordinacion_reporte_asistencia_clase", kwargs={"pk": clase.pk}),
        }

    def get_count_items(self, counts):
        return (
            {"key": "presente", "label": "Presentes", "count": counts.get("presente", 0), "icon": "ri-user-follow-line"},
            {"key": "ausente", "label": "Ausentes", "count": counts.get("ausente", 0), "icon": "ri-user-unfollow-line"},
            {"key": "atraso", "label": "Atrasos", "count": counts.get("atraso", 0), "icon": "ri-time-line"},
            {"key": "justificado", "label": "Justificados", "count": counts.get("justificado", 0), "icon": "ri-file-check-line"},
            {"key": "pendiente", "label": "Pendientes", "count": counts.get("pendiente", 0), "icon": "ri-checkbox-blank-circle-line"},
        )

    def get_card_status(self, clase, total_estudiantes, pending_count):
        if not total_estudiantes:
            return "sin-estudiantes", "Sin estudiantes"
        if clase.asistencia_cerrada:
            return "cerrada", "Cerrada"
        if pending_count:
            return "pendiente", "Pendiente"
        return "completa", "Completa"

    def get_attendance_stats(self, cards):
        stats = {
            "total": len(cards),
            "estudiantes": 0,
            "presentes": 0,
            "ausentes": 0,
            "atrasos": 0,
            "justificados": 0,
            "pendientes_registro": 0,
            "observaciones": 0,
            "cerradas": 0,
            "clases_pendientes": 0,
            "con_ausentes": 0,
            "con_observaciones": 0,
        }
        for card in cards:
            counts = card["counts"]
            stats["estudiantes"] += card["total_estudiantes"]
            stats["presentes"] += counts.get("presente", 0)
            stats["ausentes"] += counts.get("ausente", 0)
            stats["atrasos"] += counts.get("atraso", 0)
            stats["justificados"] += counts.get("justificado", 0)
            stats["pendientes_registro"] += card["pending_count"]
            stats["observaciones"] += card["observation_count"]
            if card["clase"].asistencia_cerrada:
                stats["cerradas"] += 1
            if card["pending_count"]:
                stats["clases_pendientes"] += 1
            if counts.get("ausente", 0):
                stats["con_ausentes"] += 1
            if card["observation_count"]:
                stats["con_observaciones"] += 1
        return stats

    def get_selected_filter(self, requested_filter):
        valid_filters = {item["key"] for item in self.status_filters}
        return requested_filter if requested_filter in valid_filters else "todas"

    def get_filter_label(self, selected_filter):
        filter_item = next((item for item in self.status_filters if item["key"] == selected_filter), None)
        return filter_item["label"] if filter_item else ""

    def get_status_tabs(self, selected_filter, selected_grupo, selected_docente, stats):
        base_url = reverse_lazy("academico:coordinacion_revision_asistencia")
        count_map = {
            "todas": stats["total"],
            "pendientes": stats["clases_pendientes"],
            "ausentes": stats["con_ausentes"],
            "observaciones": stats["con_observaciones"],
            "cerradas": stats["cerradas"],
        }
        tabs = []
        for item in self.status_filters:
            params = {"estado": item["key"]}
            if selected_grupo:
                params["grupo"] = selected_grupo.pk
            if selected_docente:
                params["docente"] = selected_docente.pk
            tabs.append(
                {
                    **item,
                    "count": count_map.get(item["key"], 0),
                    "url": f"{base_url}?{urlencode(params)}",
                    "is_active": item["key"] == selected_filter,
                }
            )
        return tabs

    def filter_cards(self, cards, selected_filter):
        if selected_filter == "pendientes":
            return [card for card in cards if card["pending_count"]]
        if selected_filter == "ausentes":
            return [card for card in cards if card["counts"].get("ausente", 0)]
        if selected_filter == "observaciones":
            return [card for card in cards if card["observation_count"]]
        if selected_filter == "cerradas":
            return [card for card in cards if card["clase"].asistencia_cerrada]
        return cards


class CoordinacionReporteAsistenciaClaseView(CoordinacionRevisionAsistenciaView):
    template_name = "academico/coordinacion_reporte_asistencia_clase.html"

    def get(self, request, pk):
        clase = self.get_clase()
        card = self.build_attendance_card(clase)
        return render(
            request,
            self.template_name,
            {
                "title": "Reporte de asistencia",
                "card": card,
                "clase": clase,
                "list_url": reverse_lazy("academico:coordinacion_revision_asistencia"),
            },
        )

    def get_clase(self):
        return get_object_or_404(
            self.get_clases_queryset().prefetch_related(
                Prefetch("asistencias_clase", queryset=ClaseAsistencia.objects.select_related("estudiante", "registrado_por")),
            ),
            pk=self.kwargs["pk"],
        )


class DocenteClasePlanificacionView(LoginRequiredMixin, View):
    template_name = "academico/docente_clase_planificacion.html"

    def get_clase(self):
        docente = getattr(self.request.user, "partner", None)
        if not docente or not docente.es_docente:
            return get_object_or_404(Clase.objects.none(), pk=self.kwargs["pk"])
        return get_object_or_404(
            Clase.objects.select_related(
                "materia_curso__materia",
                "materia_curso__grupo",
                "docente",
                "tema",
                "subtema",
                "horario_aula_curso__aula_curso__aula",
                "horario_aula_curso__horario_dia__horario",
            )
            .prefetch_related(
                "competencias",
                "estrategias",
                "recursos",
                Prefetch("clase_recursos", queryset=ClaseRecurso.objects.select_related("recurso")),
            )
            .filter(docente_responsable_filter(docente)),
            pk=self.kwargs["pk"],
        )

    def get(self, request, pk):
        clase = self.get_clase()
        form = DocenteClasePlanificacionForm(instance=clase, clase=clase)
        return render(request, self.template_name, self.get_context(form, clase))

    def post(self, request, pk):
        clase = self.get_clase()
        action = request.POST.get("plan_action", "send")
        form = DocenteClasePlanificacionForm(request.POST, request.FILES, instance=clase, clase=clase)
        if action not in {"draft", "send"}:
            messages.error(request, "Accion no valida.")
            return render(request, self.template_name, self.get_context(form, clase))
        if clase.estado_planificacion == "aprobada":
            messages.error(request, "La planificacion aprobada no se puede editar desde el perfil docente.")
            return render(request, self.template_name, self.get_context(form, clase))
        if form.is_valid():
            if action == "send":
                ready_errors = self.get_ready_errors(form)
                if ready_errors:
                    for error in ready_errors:
                        form.add_error(None, error)
                    return render(request, self.template_name, self.get_context(form, clase))
            with transaction.atomic():
                clase = form.save()
                self.sync_tags(clase.competencias, Competencia, "competencias")
                self.sync_tags(clase.estrategias, Estrategia, "estrategias")
                recurso_ids, new_resources_by_index = self.sync_tags(clase.recursos, Recurso, "recursos")
                self.sync_resource_files(clase, recurso_ids, new_resources_by_index)
                if action == "send":
                    clase.estado_planificacion = "revision"
                    clase.notas_revision = ""
                    clase.observaciones_revision = {}
                    clase.revisado_por = None
                    clase.fecha_revision = None
                    clase.revision_tema_ok = False
                    clase.revision_detalle_ok = False
                    clase.revision_competencias_ok = False
                    clase.revision_estrategias_ok = False
                    clase.revision_recursos_ok = False
                    clase.save(update_fields=[
                        "estado_planificacion",
                        "notas_revision",
                        "observaciones_revision",
                        "revisado_por",
                        "fecha_revision",
                        "revision_tema_ok",
                        "revision_detalle_ok",
                        "revision_competencias_ok",
                        "revision_estrategias_ok",
                        "revision_recursos_ok",
                    ])
                elif clase.estado_planificacion == "revision":
                    clase.estado_planificacion = "pendiente"
                    clase.save(update_fields=["estado_planificacion"])
            if action == "draft":
                messages.success(request, "Borrador guardado correctamente.")
                return redirect("academico:docente_clase_planificar", pk=clase.pk)
            messages.success(request, "Planificacion enviada a revision.")
            return redirect("academico:docente_horarios")
        return render(request, self.template_name, self.get_context(form, clase))

    def get_ready_errors(self, form):
        errors = []
        tema = form.cleaned_data.get("tema")
        subtema = form.cleaned_data.get("subtema")
        descripcion = (form.cleaned_data.get("descripcion") or "").strip()
        if not tema:
            errors.append("Selecciona el tema de la clase.")
        elif tema.subtemas_planificacion.exists() and not subtema:
            errors.append("Selecciona el subtema de la clase.")
        if not descripcion:
            errors.append("Escribe el detalle de la clase.")
        if not self.post_has_tag_items("competencias"):
            errors.append("Selecciona o agrega al menos una competencia.")
        if not self.post_has_tag_items("estrategias"):
            errors.append("Selecciona o agrega al menos una estrategia.")
        if not self.post_has_tag_items("recursos"):
            errors.append("Selecciona o agrega al menos un recurso.")
        return errors

    def post_has_tag_items(self, prefix):
        return bool(self.get_selected_tag_ids(prefix) or self.get_new_tag_names(prefix))

    def get_selected_tag_ids(self, prefix):
        return {
            int(value)
            for value in self.request.POST.getlist(f"{prefix}_existentes")
            if str(value).isdigit()
        }

    def sync_tags(self, relation, model, prefix):
        selected_ids = self.get_selected_tag_ids(prefix)
        new_items_by_index = {}
        for item in self.get_posted_new_tags(prefix):
            obj, _ = model.objects.get_or_create(nombre=item["nombre"])
            selected_ids.add(obj.pk)
            new_items_by_index[item["index"]] = obj
        relation.set(selected_ids)
        return selected_ids, new_items_by_index

    def sync_resource_files(self, clase, recurso_ids, new_resources_by_index):
        ClaseRecurso.objects.filter(clase=clase).exclude(recurso_id__in=recurso_ids).delete()
        for recurso_id in recurso_ids:
            clase_recurso, _ = ClaseRecurso.objects.get_or_create(clase=clase, recurso_id=recurso_id)
            uploaded = self.request.FILES.get(f"recurso_archivo_{recurso_id}")
            if uploaded:
                clase_recurso.archivo = uploaded
                clase_recurso.save(update_fields=["archivo"])
        for index, recurso in new_resources_by_index.items():
            uploaded = self.request.FILES.get(f"recursos-{index}-archivo")
            if uploaded:
                clase_recurso, _ = ClaseRecurso.objects.get_or_create(clase=clase, recurso=recurso)
                clase_recurso.archivo = uploaded
                clase_recurso.save(update_fields=["archivo"])

    def get_new_tag_names(self, prefix):
        return [item["nombre"] for item in self.get_posted_new_tags(prefix)]

    def get_posted_new_tags(self, prefix):
        try:
            total = int(self.request.POST.get(f"{prefix}-TOTAL_FORMS", 0))
        except (TypeError, ValueError):
            total = 0
        items = []
        for index in range(total):
            name = (self.request.POST.get(f"{prefix}-{index}-nombre") or "").strip()
            delete = self.request.POST.get(f"{prefix}-{index}-DELETE") == "on"
            if name and not delete:
                items.append({"index": index, "nombre": name})
        return items

    def get_context(self, form, clase):
        horario = clase.horario_aula_curso.horario_dia.horario
        temas = Tema.objects.filter(planificacion__materia_curso=clase.materia_curso).prefetch_related(
            "subtemas_planificacion"
        ).order_by("orden", "nombre")
        subtemas_by_tema = {
            str(tema.pk): [
                {"id": subtema.pk, "nombre": subtema.nombre}
                for subtema in tema.subtemas_planificacion.order_by("orden", "nombre")
            ]
            for tema in temas
        }
        observaciones = clase.observaciones_revision or {}
        clase_recursos_by_id = {
            item.recurso_id: item
            for item in clase.clase_recursos.select_related("recurso")
        }
        can_edit = clase.estado_planificacion != "aprobada"
        if not can_edit:
            for field in form.fields.values():
                field.widget.attrs["disabled"] = "disabled"
        planning_items = self.get_planning_items(clase, form)
        completed_planning_items = sum(1 for item in planning_items if item["done"])
        planning_progress = round((completed_planning_items / len(planning_items)) * 100) if planning_items else 0
        tag_groups = (
            self.build_tag_group(
                "Competencias",
                "competencias",
                Competencia.objects.order_by("nombre"),
                set(clase.competencias.values_list("id", flat=True)),
                "Agregar competencia",
                "Nueva competencia",
                observaciones.get("competencias", ""),
                "ri-medal-line",
                "seleccionadas",
            ),
            self.build_tag_group(
                "Estrategias",
                "estrategias",
                Estrategia.objects.order_by("nombre"),
                set(clase.estrategias.values_list("id", flat=True)),
                "Agregar estrategia",
                "Nueva estrategia",
                observaciones.get("estrategias", ""),
                "ri-route-line",
                "seleccionadas",
            ),
            self.build_tag_group(
                "Recursos",
                "recursos",
                Recurso.objects.order_by("nombre"),
                set(clase.recursos.values_list("id", flat=True)),
                "Agregar recurso",
                "Nuevo recurso",
                observaciones.get("recursos", ""),
                "ri-attachment-2",
                "seleccionados",
                clase_recursos_by_id,
            ),
        )
        return {
            "title": "Planificar clase",
            "form": form,
            "clase": clase,
            "horario": horario,
            "temas": temas,
            "subtemas_by_tema_json": json.dumps(subtemas_by_tema),
            "tag_groups": tag_groups,
            "clase_recursos_by_id": clase_recursos_by_id,
            "observaciones_revision": observaciones,
            "planning_items": planning_items,
            "planning_completed": completed_planning_items,
            "planning_total": len(planning_items),
            "planning_progress": planning_progress,
            "is_late": clase.fecha < timezone.localdate() and clase.estado_planificacion in {"pendiente", "rechazada"},
            "is_observed": clase.estado_planificacion == "rechazada",
            "is_submitted": clase.estado_planificacion == "revision",
            "can_edit": can_edit,
            "cancel_url": reverse_lazy("academico:docente_horarios"),
            "attendance_url": reverse_lazy("academico:docente_clase_asistencia", kwargs={"pk": clase.pk}),
        }

    def get_planning_items(self, clase, form):
        if form.is_bound:
            tema_done = bool((form.data.get("tema") or "").strip())
            descripcion_done = bool((form.data.get("descripcion") or "").strip())
            competencias_done = self.post_has_tag_items("competencias")
            estrategias_done = self.post_has_tag_items("estrategias")
            recursos_done = self.post_has_tag_items("recursos")
        else:
            tema_done = bool(clase.tema_id)
            descripcion_done = bool(clase.descripcion)
            competencias_done = clase.competencias.exists()
            estrategias_done = clase.estrategias.exists()
            recursos_done = clase.recursos.exists()
        observaciones = clase.observaciones_revision or {}
        return [
            {"key": "tema", "label": "Tema", "done": tema_done, "note": observaciones.get("tema", "")},
            {"key": "detalle", "label": "Detalle", "done": descripcion_done, "note": observaciones.get("detalle", "")},
            {"key": "competencias", "label": "Competencias", "done": competencias_done, "note": observaciones.get("competencias", "")},
            {"key": "estrategias", "label": "Estrategias", "done": estrategias_done, "note": observaciones.get("estrategias", "")},
            {"key": "recursos", "label": "Recursos", "done": recursos_done, "note": observaciones.get("recursos", "")},
        ]

    def build_tag_group(
        self,
        title,
        prefix,
        queryset,
        selected_ids,
        add_label,
        placeholder,
        revision_note,
        icon,
        count_label,
        clase_recursos_by_id=None,
    ):
        if self.request.method == "POST":
            selected_ids = self.get_selected_tag_ids(prefix)
        items = []
        for obj in queryset:
            clase_recurso = (clase_recursos_by_id or {}).get(obj.pk)
            file_meta = file_attachment_meta(clase_recurso.archivo) if clase_recurso else None
            items.append(
                {
                    "obj": obj,
                    "selected": obj.pk in selected_ids,
                    "clase_recurso": clase_recurso,
                    "file_meta": file_meta,
                }
            )
        return {
            "title": title,
            "prefix": prefix,
            "items": items,
            "selected_count": len(selected_ids),
            "add_label": add_label,
            "placeholder": placeholder,
            "revision_note": revision_note,
            "new_entries": self.get_posted_new_tags(prefix) if self.request.method == "POST" else [],
            "icon": icon,
            "count_label": count_label,
        }


class CoordinacionRevisionPlanificacionesView(CoordinacionRequiredMixin, View):
    template_name = "academico/coordinacion_revision_planificaciones.html"
    status_filters = (
        {
            "key": "revision",
            "label": "Enviadas",
            "states": ("revision",),
            "icon": "ri-send-plane-line",
        },
        {
            "key": "pendiente",
            "label": "Sin enviar",
            "states": ("pendiente",),
            "icon": "ri-draft-line",
        },
        {
            "key": "atrasadas",
            "label": "Atrasadas",
            "states": None,
            "late": True,
            "icon": "ri-alarm-warning-line",
        },
        {
            "key": "rechazada",
            "label": "Observadas",
            "states": ("rechazada",),
            "icon": "ri-error-warning-line",
        },
        {
            "key": "aprobada",
            "label": "Aprobadas",
            "states": ("aprobada",),
            "icon": "ri-checkbox-circle-line",
        },
        {
            "key": "todas",
            "label": "Todas",
            "states": None,
            "icon": "ri-list-check-3",
        },
    )

    def get(self, request):
        estado = request.GET.get("estado", "")
        q = (request.GET.get("q") or "").strip()
        selected_docente = self.get_selected_docente()
        clases_queryset = self.get_clases_queryset()

        if selected_docente:
            clases_queryset = clases_queryset.filter(docente_responsable_filter(selected_docente))
        if q:
            clases_queryset = clases_queryset.filter(
                Q(materia_curso__materia__nombre__icontains=q)
                | Q(materia_curso__grupo__nombre__icontains=q)
                | Q(tema__nombre__icontains=q)
                | Q(subtema__nombre__icontains=q)
                | docente_responsable_search_filter(q)
            )
        clases = list(clases_queryset.distinct())
        stats = self.get_revision_stats(clases)
        selected_estado = self.get_selected_filter(estado, stats)
        revision_cards = [
            self.build_revision_card(clase)
            for clase in self.filter_clases(clases, selected_estado)
        ]
        return render(
            request,
            self.template_name,
            {
                "title": "Revision de planificaciones",
                "clases": clases,
                "revision_cards": revision_cards,
                "revision_stats": stats,
                "docentes": Partner.objects.filter(es_docente=True, activo=True).order_by("nombre"),
                "selected_docente": selected_docente,
                "selected_docente_id": selected_docente.pk if selected_docente else "",
                "selected_estado_label": self.get_filter_label(selected_estado),
                "status_tabs": self.get_status_tabs(selected_estado, selected_docente, q, stats),
                "estado_choices": Clase.ESTADO_PLANIFICACION_CHOICES,
                "selected_estado": selected_estado,
                "search_query": q,
                "unassigned_alert": clases_sin_docente_alert(),
            },
        )

    def get_clases_queryset(self):
        return (
            Clase.objects.select_related(
                "materia_curso__materia",
                "materia_curso__grupo",
                "docente",
                "tema",
                "subtema",
                "horario_aula_curso__aula_curso__aula",
                "horario_aula_curso__horario_dia__horario",
            )
            .prefetch_related(
                "competencias",
                "estrategias",
                "recursos",
                "materia_curso__profesor_materia_cursos__partner",
            )
            .order_by("fecha", "horario_aula_curso__horario_dia__horario__hora_inicio", "materia_curso__grupo__nombre")
        )

    def get_selected_docente(self):
        docente_id = self.request.GET.get("docente") or ""
        if not docente_id:
            return None
        return Partner.objects.filter(pk=docente_id, es_docente=True, activo=True).first()

    def empty_revision_stats(self):
        return {
            "total": 0,
            "pendiente": 0,
            "revision": 0,
            "rechazada": 0,
            "aprobada": 0,
            "atrasadas": 0,
        }

    def get_revision_stats(self, clases):
        stats = self.empty_revision_stats()
        stats["total"] = len(clases)
        for clase in clases:
            if clase.estado_planificacion in stats:
                stats[clase.estado_planificacion] += 1
            if self.is_late(clase):
                stats["atrasadas"] += 1
        return stats

    def is_late(self, clase):
        return clase.fecha < timezone.localdate() and clase.estado_planificacion in {"pendiente", "rechazada"}

    def get_selected_filter(self, requested_filter, stats):
        valid_filters = {item["key"] for item in self.status_filters}
        if requested_filter in valid_filters:
            return requested_filter
        if stats["revision"]:
            return "revision"
        if stats["atrasadas"]:
            return "atrasadas"
        if stats["pendiente"]:
            return "pendiente"
        return "todas"

    def get_filter_label(self, selected_filter):
        filter_item = next((item for item in self.status_filters if item["key"] == selected_filter), None)
        return filter_item["label"] if filter_item else ""

    def get_status_tabs(self, selected_filter, selected_docente, q, stats):
        base_url = reverse_lazy("academico:coordinacion_revision_planificaciones")
        tabs = []
        for item in self.status_filters:
            if item.get("late"):
                count = stats["atrasadas"]
            elif item["states"] is None:
                count = stats["total"]
            else:
                count = sum(stats[state] for state in item["states"])
            params = {"estado": item["key"]}
            if selected_docente:
                params["docente"] = selected_docente.pk
            if q:
                params["q"] = q
            tabs.append(
                {
                    **item,
                    "count": count,
                    "url": f"{base_url}?{urlencode(params)}",
                    "is_active": item["key"] == selected_filter,
                }
            )
        return tabs

    def filter_clases(self, clases, selected_filter):
        filter_item = next((item for item in self.status_filters if item["key"] == selected_filter), None)
        if not filter_item or selected_filter == "todas":
            return clases
        if filter_item.get("late"):
            return [clase for clase in clases if self.is_late(clase)]
        allowed_states = set(filter_item["states"] or [])
        return [clase for clase in clases if clase.estado_planificacion in allowed_states]

    def build_revision_card(self, clase):
        horario = clase.horario_aula_curso.horario_dia.horario
        docentes = get_clase_docentes(clase)
        competencias = list(clase.competencias.all())
        estrategias = list(clase.estrategias.all())
        recursos = list(clase.recursos.all())
        observaciones = clase.observaciones_revision or {}
        steps = [
            {"label": "Tema", "done": bool(clase.tema_id), "note": observaciones.get("tema", "")},
            {"label": "Detalle", "done": bool(clase.descripcion), "note": observaciones.get("detalle", "")},
            {"label": "Competencias", "done": bool(competencias), "note": observaciones.get("competencias", "")},
            {"label": "Estrategias", "done": bool(estrategias), "note": observaciones.get("estrategias", "")},
            {"label": "Recursos", "done": bool(recursos), "note": observaciones.get("recursos", "")},
        ]
        completed_steps = sum(1 for step in steps if step["done"])
        action_labels = {
            "pendiente": "Ver pendiente",
            "revision": "Revisar",
            "rechazada": "Ver observacion",
            "aprobada": "Ver aprobada",
        }
        return {
            "clase": clase,
            "horario": horario,
            "estado": clase.estado_planificacion,
            "estado_label": clase.get_estado_planificacion_display(),
            "grupo": clase.materia_curso.grupo,
            "materia": clase.materia_curso.materia,
            "aula": clase.horario_aula_curso.aula_curso.aula,
            "docentes": docentes,
            "tema": clase.tema,
            "subtema": clase.subtema,
            "steps": steps,
            "progress": round((completed_steps / len(steps)) * 100),
            "is_late": self.is_late(clase),
            "is_unsent": clase.estado_planificacion == "pendiente",
            "revision_note": clase.notas_revision if clase.estado_planificacion == "rechazada" else "",
            "action_label": action_labels.get(clase.estado_planificacion, "Abrir"),
            "url": reverse_lazy("academico:coordinacion_revision_planificacion_detalle", kwargs={"pk": clase.pk}),
        }


class CoordinacionRevisionPlanificacionDetalleView(CoordinacionRequiredMixin, View):
    template_name = "academico/coordinacion_revision_planificacion_detalle.html"

    def get_clase(self):
        return get_object_or_404(
            Clase.objects.select_related(
                "materia_curso__materia",
                "materia_curso__grupo",
                "docente",
                "tema",
                "subtema",
                "horario_aula_curso__aula_curso__aula",
                "horario_aula_curso__horario_dia__horario",
            ).prefetch_related(
                "competencias",
                "estrategias",
                "recursos",
                Prefetch("clase_recursos", queryset=ClaseRecurso.objects.select_related("recurso")),
                "materia_curso__profesor_materia_cursos__partner",
            ),
            pk=self.kwargs["pk"],
        )

    def get(self, request, pk):
        return render(request, self.template_name, self.get_context(self.get_clase()))

    def post(self, request, pk):
        clase = self.get_clase()
        action = request.POST.get("review_action")
        notas = request.POST.get("notas_revision", "").strip()
        if action == "rechazar" and not notas:
            messages.error(request, "Escribe observaciones para rechazar la planificacion.")
            return render(request, self.template_name, self.get_context(clase))
        if action not in {"aprobar", "rechazar"}:
            messages.error(request, "Accion no valida.")
            return render(request, self.template_name, self.get_context(clase))
        if action == "aprobar" and not clase_tiene_docente(clase):
            messages.error(request, "Asigna un docente a la materia del grupo antes de aprobar la planificacion.")
            return render(request, self.template_name, self.get_context(clase))
        clase.revision_tema_ok = request.POST.get("revision_tema_ok") == "on"
        clase.revision_detalle_ok = request.POST.get("revision_detalle_ok") == "on"
        clase.revision_competencias_ok = request.POST.get("revision_competencias_ok") == "on"
        clase.revision_estrategias_ok = request.POST.get("revision_estrategias_ok") == "on"
        clase.revision_recursos_ok = request.POST.get("revision_recursos_ok") == "on"
        section_comments = self.get_section_comments(request)
        unchecked_sections = [
            label
            for key, label in self.review_sections()
            if not getattr(clase, f"revision_{key}_ok")
        ]
        if action == "aprobar" and unchecked_sections:
            messages.error(request, "Marca todos los puntos como correctos antes de aprobar.")
            return render(request, self.template_name, self.get_context(clase))
        if action == "rechazar":
            if not unchecked_sections:
                messages.error(request, "Para devolver la planificacion, deja al menos un punto observado.")
                return render(request, self.template_name, self.get_context(clase))
            missing = [
                label
                for key, label in self.review_sections()
                if not getattr(clase, f"revision_{key}_ok") and not section_comments.get(key)
            ]
            if missing:
                messages.error(request, "Agrega comentario en: " + ", ".join(missing))
                return render(request, self.template_name, self.get_context(clase))
        clase.estado_planificacion = "aprobada" if action == "aprobar" else "rechazada"
        clase.notas_revision = notas
        clase.observaciones_revision = {} if action == "aprobar" else section_comments
        clase.revisado_por = getattr(request.user, "partner", None)
        clase.fecha_revision = timezone.now()
        clase.save(update_fields=[
            "estado_planificacion",
            "notas_revision",
            "observaciones_revision",
            "revisado_por",
            "fecha_revision",
            "revision_tema_ok",
            "revision_detalle_ok",
            "revision_competencias_ok",
            "revision_estrategias_ok",
            "revision_recursos_ok",
        ])
        messages.success(request, "Revision registrada correctamente.")
        return redirect("academico:coordinacion_revision_planificaciones")

    def review_sections(self):
        return (
            ("tema", "Tema y subtema"),
            ("detalle", "Detalle"),
            ("competencias", "Competencias"),
            ("estrategias", "Estrategias"),
            ("recursos", "Recursos"),
        )

    def get_section_comments(self, request):
        comments = {}
        for key, _ in self.review_sections():
            if request.POST.get(f"revision_{key}_ok") == "on":
                continue
            value = request.POST.get(f"observacion_{key}", "").strip()
            if value:
                comments[key] = value
        return comments

    def get_context(self, clase):
        horario = clase.horario_aula_curso.horario_dia.horario
        docentes = get_clase_docentes(clase)
        observaciones = clase.observaciones_revision or {}
        review_items = [
            {
                "key": key,
                "label": label,
                "ok": getattr(clase, f"revision_{key}_ok"),
                "comment": observaciones.get(key, ""),
            }
            for key, label in self.review_sections()
        ]
        planning_items = [
            {"label": "Tema", "done": bool(clase.tema_id)},
            {"label": "Detalle", "done": bool(clase.descripcion)},
            {"label": "Competencias", "done": clase.competencias.exists()},
            {"label": "Estrategias", "done": clase.estrategias.exists()},
            {"label": "Recursos", "done": clase.recursos.exists()},
        ]
        completed_planning_items = sum(1 for item in planning_items if item["done"])
        checked_review_items = sum(1 for item in review_items if item["ok"])
        return {
            "title": "Revisar planificacion",
            "clase": clase,
            "horario": horario,
            "docentes": docentes,
            "tiene_docente": bool(docentes),
            "resource_items": self.get_resource_items(clase),
            "review_items": review_items,
            "review_total": len(review_items),
            "review_checked": checked_review_items,
            "review_progress": round((checked_review_items / len(review_items)) * 100) if review_items else 0,
            "planning_items": planning_items,
            "planning_progress": round((completed_planning_items / len(planning_items)) * 100) if planning_items else 0,
            "is_late": clase.fecha < timezone.localdate() and clase.estado_planificacion in {"pendiente", "rechazada"},
            "is_unsent": clase.estado_planificacion == "pendiente",
            "observaciones_revision": observaciones,
            "list_url": reverse_lazy("academico:coordinacion_revision_planificaciones"),
            "planificacion_docente_url": reverse_lazy("academico:planificacion_docente"),
        }

    def get_resource_items(self, clase):
        return [
            {
                "clase_recurso": item,
                "recurso": item.recurso,
                "archivo": item.archivo,
                "file_meta": file_attachment_meta(item.archivo),
            }
            for item in clase.clase_recursos.all()
        ]


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
    create_url_name = "academico:horario_asignacion"
    update_url_name = "academico:horario_editar"
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
        user = self.request.user
        if not can_view_all_horarios(user):
            queryset = queryset.filter(docente__usuario=user)
        q = self.request.GET.get("q")
        if q:
            queryset = queryset.filter(
                Q(aula__nombre__icontains=q)
                | Q(asignatura__nombre__icontains=q)
                | Q(docente__nombre__icontains=q)
                | Q(tutor__nombre__icontains=q)
                | Q(periodo_academico__nombre__icontains=q)
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


class HorarioAsignacionView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "academico.add_horarioclase"
    template_name = "academico/horario_asignacion.html"

    def get_empresa(self):
        return Empresa.objects.filter(activa=True).first() or Empresa.objects.first()

    def get(self, request):
        empresa = self.get_empresa()
        initial = {}
        if empresa:
            periodo = empresa.periodoacademico_set.filter(activo=True).order_by("-fecha_inicio", "nombre").first()
            initial["periodo_academico"] = getattr(periodo, "pk", None)
            if periodo and periodo.fecha_inicio:
                initial["fecha_inicio"] = periodo.fecha_inicio.isoformat()
            if periodo and periodo.fecha_fin:
                initial["fecha_fin"] = periodo.fecha_fin.isoformat()
            initial["aula"] = getattr(empresa.aula_set.filter(activo=True).first(), "pk", None)
        selected_date = request.GET.get("date")
        if selected_date:
            try:
                parsed_date = date.fromisoformat(selected_date)
                initial["fecha_inicio"] = parsed_date.isoformat()
                initial["fecha_fin"] = parsed_date.isoformat()
                initial["dias_semana"] = [str(parsed_date.weekday())]
            except ValueError:
                pass
        if request.GET.get("aula"):
            initial["aula"] = request.GET.get("aula")
        if request.GET.get("periodo"):
            initial["periodo_academico"] = request.GET.get("periodo")
        base_form = HorarioAsignacionBaseForm(empresa=empresa, initial=initial)
        formset = HorarioAsignacionFormSet(form_kwargs={"empresa": empresa})
        return render(request, self.template_name, self.get_context(base_form, formset))

    def post(self, request):
        empresa = self.get_empresa()
        base_form = HorarioAsignacionBaseForm(request.POST, empresa=empresa)
        formset = HorarioAsignacionFormSet(request.POST, form_kwargs={"empresa": empresa})
        saved = 0
        skipped = 0
        if base_form.is_valid():
            periodo = base_form.cleaned_data["periodo_academico"]
            aula = base_form.cleaned_data["aula"]
            current_date = base_form.cleaned_data["fecha_inicio"]
            end_date = base_form.cleaned_data["fecha_fin"]
            weekdays = {int(day) for day in base_form.cleaned_data["dias_semana"]}
            while current_date <= end_date:
                if current_date.weekday() not in weekdays:
                    current_date += timedelta(days=1)
                    continue
                horario = HorarioClase(
                    empresa=empresa,
                    periodo_academico=periodo,
                    aula=aula,
                    fecha=current_date,
                    hora_inicio=base_form.cleaned_data["hora_inicio"],
                    hora_fin=base_form.cleaned_data["hora_fin"],
                    asignatura=base_form.cleaned_data["asignatura"],
                    docente=base_form.cleaned_data["docente"],
                    tutor=base_form.cleaned_data.get("tutor"),
                    estado="programada",
                    activo=True,
                    usuario_updated=request.user,
                )
                try:
                    horario.full_clean()
                    horario.save()
                    PlanificacionClase.objects.get_or_create(
                        horario_clase=horario,
                        defaults={
                            "empresa": empresa,
                            "docente": horario.docente,
                            "aula": horario.aula,
                            "asignatura": horario.asignatura,
                            "fecha_planificada": horario.fecha,
                            "objetivo": "",
                            "estado": "pendiente",
                            "activo": True,
                            "usuario_updated": request.user,
                        },
                    )
                    saved += 1
                except ValidationError:
                    skipped += 1
                current_date += timedelta(days=1)
            if saved:
                message = f"{saved} clase(s) programada(s)."
                if skipped:
                    message += f" {skipped} no se crearon por cruces de aula o docente."
                messages.success(request, message)
                return redirect("academico:horario_calendario")
            if skipped:
                base_form.add_error(None, "No se crearon horarios porque todos cruzan con otra clase del aula o docente.")
        return render(request, self.template_name, self.get_context(base_form, formset))

    def get_context(self, base_form, formset):
        return {
            "title": "Asignar horarios",
            "base_form": base_form,
            "formset": formset,
            "calendar_url": reverse_lazy("academico:horario_calendario"),
            "cancel_url": reverse_lazy("academico:horario_list"),
        }


class HorarioCalendarioView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "academico.view_horarioclase"
    template_name = "academico/horario_calendario.html"
    month_names = (
        "",
        "Enero",
        "Febrero",
        "Marzo",
        "Abril",
        "Mayo",
        "Junio",
        "Julio",
        "Agosto",
        "Septiembre",
        "Octubre",
        "Noviembre",
        "Diciembre",
    )

    def get_month_date(self, request, queryset):
        today = timezone.localdate()
        first_horario = queryset.order_by("fecha", "hora_inicio").first()
        default_date = first_horario.fecha if first_horario else today
        try:
            year = int(request.GET.get("year") or default_date.year)
            month = int(request.GET.get("month") or default_date.month)
            return date(year, month, 1)
        except (TypeError, ValueError):
            return date(default_date.year, default_date.month, 1)

    def get_focus_date(self, request, queryset):
        month_date = self.get_month_date(request, queryset)
        try:
            return date.fromisoformat(request.GET.get("date") or month_date.isoformat())
        except ValueError:
            return month_date

    def build_calendar_url(self, target_date, filters, view_mode="month"):
        params = {"view": view_mode, "date": target_date.isoformat(), "year": target_date.year, "month": target_date.month}
        params.update({key: value for key, value in filters.items() if value})
        return f"?{urlencode(params)}"

    def can_view_all(self, user):
        return can_view_all_horarios(user)

    def get(self, request):
        can_add_horario = request.user.has_perm("academico.add_horarioclase")
        can_change_horario = request.user.has_perm("academico.change_horarioclase")
        queryset = (
            HorarioClase.objects.select_related("periodo_academico", "aula", "asignatura", "docente", "tutor")
            .filter(activo=True)
            .order_by("fecha", "hora_inicio", "aula__nombre")
        )
        can_view_all = self.can_view_all(request.user)
        if not can_view_all:
            queryset = queryset.filter(docente__usuario=request.user)
        options_queryset = queryset
        periodo_id = request.GET.get("periodo")
        aula_id = request.GET.get("aula")
        if periodo_id:
            queryset = queryset.filter(periodo_academico_id=periodo_id)
        if aula_id:
            queryset = queryset.filter(aula_id=aula_id)
        sidebar_horarios = list(queryset)
        for index, horario in enumerate(sidebar_horarios):
            horario.color_index = (index % 5) + 1

        view_mode = request.GET.get("view") if request.GET.get("view") in {"day", "week", "month"} else "month"
        focus_date = self.get_focus_date(request, queryset)
        month_date = focus_date.replace(day=1)
        next_month = (month_date.replace(day=28) + timedelta(days=4)).replace(day=1)
        previous_month = (month_date - timedelta(days=1)).replace(day=1)
        month_end = next_month - timedelta(days=1)
        month_horarios = list(queryset.filter(fecha__range=(month_date, month_end)))

        horarios_by_date = {}
        for index, horario in enumerate(month_horarios):
            horario.color_index = (index % 5) + 1
            horarios_by_date.setdefault(horario.fecha, []).append(horario)

        calendar_weeks = []
        month_calendar = calendar_module.Calendar(firstweekday=0)
        for week in month_calendar.monthdatescalendar(month_date.year, month_date.month):
            calendar_weeks.append(
                [
                    {
                        "date": day,
                        "in_month": day.month == month_date.month,
                        "is_today": day == timezone.localdate(),
                        "is_selected": day == focus_date,
                        "url": self.build_calendar_url(day, {"periodo": periodo_id or "", "aula": aula_id or ""}, view_mode),
                        "horarios": horarios_by_date.get(day, []),
                    }
                    for day in week
                ]
            )

        today_month = timezone.localdate().replace(day=1)
        filters = {"periodo": periodo_id or "", "aula": aula_id or ""}
        week_start = focus_date - timedelta(days=focus_date.weekday())
        week_days = []
        for offset in range(7):
            day = week_start + timedelta(days=offset)
            week_horarios = list(queryset.filter(fecha=day))
            for index, horario in enumerate(week_horarios):
                horario.color_index = (index % 5) + 1
            week_days.append(
                {
                    "date": day,
                    "is_today": day == timezone.localdate(),
                    "is_selected": day == focus_date,
                    "url": self.build_calendar_url(day, filters, "week"),
                    "horarios": week_horarios,
                }
            )
        day_horarios = list(queryset.filter(fecha=focus_date))
        for index, horario in enumerate(day_horarios):
            horario.color_index = (index % 5) + 1
        selected_date_label = f"{focus_date.day} {self.month_names[focus_date.month]} {focus_date.year}"
        assign_selected_url = reverse_lazy("academico:horario_asignacion")
        assign_params = {"date": focus_date.isoformat(), "periodo": periodo_id or "", "aula": aula_id or ""}
        assign_selected_url = f"{assign_selected_url}?{urlencode({k: v for k, v in assign_params.items() if v})}"
        if view_mode == "day":
            previous_url = self.build_calendar_url(focus_date - timedelta(days=1), filters, view_mode)
            next_url = self.build_calendar_url(focus_date + timedelta(days=1), filters, view_mode)
        elif view_mode == "week":
            previous_url = self.build_calendar_url(focus_date - timedelta(days=7), filters, view_mode)
            next_url = self.build_calendar_url(focus_date + timedelta(days=7), filters, view_mode)
        else:
            previous_url = self.build_calendar_url(previous_month, filters, view_mode)
            next_url = self.build_calendar_url(next_month, filters, view_mode)
        event_classes = ("important", "success", "info", "chill", "")
        calendar_events = []
        for index, horario in enumerate(queryset):
            calendar_events.append(
                {
                    "id": horario.pk,
                    "title": f"{horario.asignatura} · {horario.aula}",
                    "start": f"{horario.fecha.isoformat()}T{horario.hora_inicio.strftime('%H:%M:%S')}",
                    "end": f"{horario.fecha.isoformat()}T{horario.hora_fin.strftime('%H:%M:%S')}",
                    "allDay": False,
                    "className": event_classes[index % len(event_classes)],
                    "url": str(reverse_lazy("academico:horario_editar", kwargs={"pk": horario.pk})) if can_change_horario else "",
                    "description": f"{horario.hora_inicio:%H:%M} - {horario.hora_fin:%H:%M} · {horario.asignatura} · {horario.aula} · {horario.docente}",
                }
            )

        return render(
            request,
            self.template_name,
            {
                "title": "Calendario de horarios",
                "view_mode": view_mode,
                "month_label": f"{self.month_names[month_date.month]} {month_date.year}",
                "selected_date_label": selected_date_label,
                "selected_date_iso": focus_date.isoformat(),
                "calendar_weeks": calendar_weeks,
                "week_days": week_days,
                "day_horarios": day_horarios,
                "month_horarios": month_horarios[:14],
                "calendar_sidebar_horarios": sidebar_horarios,
                "periodos": options_queryset.values_list("periodo_academico_id", "periodo_academico__nombre")
                .distinct()
                .order_by("periodo_academico__nombre"),
                "aulas": options_queryset.values_list("aula_id", "aula__nombre").distinct().order_by("aula__nombre"),
                "selected_periodo": periodo_id or "",
                "selected_aula": aula_id or "",
                "can_view_all_horarios": can_view_all,
                "can_add_horario": can_add_horario,
                "can_change_horario": can_change_horario,
                "day_view_url": self.build_calendar_url(focus_date, filters, "day"),
                "week_view_url": self.build_calendar_url(focus_date, filters, "week"),
                "month_view_url": self.build_calendar_url(focus_date, filters, "month"),
                "previous_month_url": previous_url,
                "next_month_url": next_url,
                "today_url": self.build_calendar_url(today_month, filters, view_mode),
                "assign_selected_url": assign_selected_url,
                "calendar_events_json": json.dumps(calendar_events),
                "calendar_default_view": {"day": "agendaDay", "week": "agendaWeek", "month": "month"}[view_mode],
                "calendar_default_date": focus_date.isoformat(),
                "current_year": month_date.year,
                "current_month": month_date.month,
            },
        )


class TemaListView(InstitutoListView):
    model = Tema
    title = "Temas"
    create_url_name = "academico:tema_nuevo"
    columns = (("Planificacion", "planificacion"), ("Orden", "orden"), ("Nombre", "nombre"), ("Detalle", "detalle"))

    def get_queryset(self):
        return super().get_queryset().select_related("planificacion", "planificacion__materia_curso")


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
    template_name = "academico/planificacion_list.html"
    title = "Planificacion de clases"
    update_url_name = "academico:planificacion_editar"
    columns = (
        ("Fecha", "fecha_planificada"),
        ("Docente", "docente"),
        ("Aula", "aula"),
        ("Asignatura", "asignatura"),
        ("Tema", "tema"),
        ("Estado", "estado"),
    )

    def get_queryset(self):
        queryset = super().get_queryset().select_related("docente", "aula", "asignatura", "tema", "empresa", "horario_clase")
        user = self.request.user
        if not user.is_superuser and not user.groups.filter(name="Director").exists():
            queryset = queryset.filter(docente__usuario=user)
        estado = self.request.GET.get("estado")
        if estado:
            queryset = queryset.filter(estado=estado)
        q = self.request.GET.get("q")
        if q:
            queryset = queryset.filter(
                Q(docente__nombre__icontains=q)
                | Q(aula__nombre__icontains=q)
                | Q(asignatura__nombre__icontains=q)
                | Q(tema__nombre__icontains=q)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["estado_choices"] = PlanificacionClase.ESTADO_CHOICES
        context["selected_estado"] = self.request.GET.get("estado", "")
        return context

    def get_action_label(self, obj):
        return "Revisar"


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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["planificacion_resumen"] = self.object
        user = self.request.user
        can_review = (
            user.is_superuser
            or user.groups.filter(name="Director").exists()
            or user.has_perm("academico.review_planificacionclase")
        )
        context["review_enabled"] = can_review and self.object.estado == "revision"
        context["show_save_button"] = (not can_review) and self.object.estado in {"pendiente", "rechazada"}
        return context

    def get_queryset(self):
        queryset = super().get_queryset().select_related("docente")
        user = self.request.user
        if not user.is_superuser and not user.groups.filter(name="Director").exists():
            queryset = queryset.filter(docente__usuario=user)
        return queryset

    def form_valid(self, form):
        user = self.request.user
        if not user.is_superuser and not user.groups.filter(name="Director").exists():
            if form.instance.estado in {"pendiente", "rechazada"}:
                form.instance.estado = "revision"
        return super().form_valid(form)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        review_action = request.POST.get("review_action")
        user = request.user
        can_review = (
            user.is_superuser
            or user.groups.filter(name="Director").exists()
            or user.has_perm("academico.review_planificacionclase")
        )
        if review_action and can_review:
            self.object.notas_revision = request.POST.get("notas_revision", "")
            self.object.fecha_revision = timezone.now()
            if review_action == "aprobar":
                self.object.estado = "aprobada"
                messages.success(request, "Planificacion aprobada.")
            elif review_action == "rechazar":
                if not self.object.notas_revision.strip():
                    messages.error(request, "Escribe observaciones para devolver la planificacion.")
                    return redirect(request.path)
                self.object.estado = "rechazada"
                messages.success(request, "Planificacion rechazada y devuelta para subsanar.")
            self.object.usuario_updated = request.user
            self.object.save(update_fields=["notas_revision", "fecha_revision", "estado", "usuario_updated", "updated"])
            return redirect(self.success_url)
        return super().post(request, *args, **kwargs)


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
