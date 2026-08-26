import calendar as calendar_module
import json
from io import BytesIO
from datetime import date, timedelta
from urllib.parse import urlencode

from django.http import HttpResponse
from django.urls import reverse_lazy
from django.db import transaction
from django.db.models import Prefetch
from django.db.models import Count, Q
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

from .forms import (
    AsignaturaForm,
    AulaForm,
    BancoPreguntaForm,
    CursoForm,
    HorarioDistribucionBaseForm,
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
    Curso,
    CursoPeriodo,
    Dia,
    Horario,
    HorarioAulaCurso,
    HorarioClase,
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
            Curso.objects.filter(aula_cursos__horario_aula_cursos__isnull=False)
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
                    HorarioAulaCurso.objects.filter(aula_curso__curso=curso).delete()
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
        if not (
            request.user.has_perm("academico.add_clase")
            or request.user.has_perm("academico.change_clase")
            or request.user.is_superuser
        ):
            return self.handle_no_permission()

        curso = get_object_or_404(Curso, pk=request.POST.get("curso"))
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
            weekday_to_dia = {
                0: "Lunes",
                1: "Martes",
                2: "Miercoles",
                3: "Jueves",
                4: "Viernes",
                5: "Sabado",
                6: "Domingo",
            }
            if not curso_periodo or horario_aula_curso.horario_dia.dia.dia != weekday_to_dia[fecha_clase.weekday()]:
                messages.error(request, "La fecha seleccionada no corresponde al horario del grupo.")
                return redirect(f"{reverse_lazy('academico:planificacion_academica')}?curso={curso.pk}")

            materia_id = request.POST.get("materia") or ""
            asignar_periodo = request.POST.get("asignar_periodo") == "on"
            with transaction.atomic():
                Clase.objects.filter(horario_aula_curso=horario_aula_curso, fecha=fecha_clase).delete()
                if materia_id:
                    materia = get_object_or_404(Materia, pk=materia_id)
                    materia_grupo, _ = MateriaCurso.objects.get_or_create(
                        materia=materia,
                        grupo=curso,
                    )
                    Clase.objects.create(
                        horario_aula_curso=horario_aula_curso,
                        materia_curso=materia_grupo,
                        fecha=fecha_clase,
                    )
                    created_count = 1
                    if asignar_periodo:
                        current_date = curso_periodo.periodo.fecha_inicio
                        while current_date <= curso_periodo.periodo.fecha_fin:
                            if (
                                current_date != fecha_clase
                                and weekday_to_dia[current_date.weekday()] == horario_aula_curso.horario_dia.dia.dia
                            ):
                                _, created = Clase.objects.get_or_create(
                                    horario_aula_curso=horario_aula_curso,
                                    fecha=current_date,
                                    defaults={"materia_curso": materia_grupo},
                                )
                                if created:
                                    created_count += 1
                            current_date += timedelta(days=1)
                    if asignar_periodo:
                        messages.success(request, f"Clase asignada correctamente en {created_count} fecha(s) libre(s).")
                    else:
                        messages.success(request, "Clase asignada correctamente.")
                else:
                    messages.success(request, "Clase removida correctamente.")
            return redirect(f"{reverse_lazy('academico:planificacion_academica')}?curso={curso.pk}")

        messages.error(request, "Selecciona un horario del calendario para asignar la clase.")
        return redirect(f"{reverse_lazy('academico:planificacion_academica')}?curso={curso.pk}")

    def get_context(self):
        cursos = Curso.objects.filter(activo=True).order_by("nombre")
        materias = Materia.objects.order_by("nombre")
        selected_curso_id = self.request.GET.get("curso") or ""
        selected_curso = None
        selected_curso_periodo = None
        rows = []
        calendar_events = []
        calendar_default_date = timezone.localdate().isoformat()

        if selected_curso_id:
            selected_curso = get_object_or_404(Curso, pk=selected_curso_id)
            selected_curso_periodo = (
                CursoPeriodo.objects.select_related("periodo")
                .filter(curso=selected_curso)
                .order_by("-periodo__fecha_inicio")
                .first()
            )
            horarios = (
                HorarioAulaCurso.objects.select_related(
                    "aula_curso__aula",
                    "aula_curso__curso",
                    "horario_dia__dia",
                    "horario_dia__horario",
                )
                .filter(aula_curso__curso=selected_curso)
                .order_by(
                    "horario_dia__horario__hora_inicio",
                    "horario_dia__horario__hora_fin",
                    "horario_dia__dia__id",
                    "aula_curso__aula__nombre",
                )
            )
            clases = {}
            docentes_by_materia_curso = {}
            if selected_curso_periodo:
                clases = {
                    (item.horario_aula_curso_id, item.fecha): item
                    for item in Clase.objects.select_related("materia_curso__materia").filter(
                        horario_aula_curso__in=horarios,
                        fecha__gte=selected_curso_periodo.periodo.fecha_inicio,
                        fecha__lte=selected_curso_periodo.periodo.fecha_fin,
                    )
                }
                docentes_by_materia_curso = {
                    item.materia_curso_id: item.partner
                    for item in ProfesorMateriaCurso.objects.select_related("partner").filter(
                        materia_curso__grupo=selected_curso,
                    )
                }
            weekday_to_dia = {
                0: "Lunes",
                1: "Martes",
                2: "Miercoles",
                3: "Jueves",
                4: "Viernes",
                5: "Sabado",
                6: "Domingo",
            }
            if selected_curso_periodo:
                current_date = selected_curso_periodo.periodo.fecha_inicio
                end_date = selected_curso_periodo.periodo.fecha_fin
                calendar_default_date = current_date.isoformat()
                while current_date <= end_date:
                    day_name = weekday_to_dia[current_date.weekday()]
                    day_horarios = [
                        horario_aula_curso
                        for horario_aula_curso in horarios
                        if horario_aula_curso.horario_dia.dia.dia == day_name
                    ]
                    blocks = []
                    for horario_aula_curso in horarios:
                        if horario_aula_curso not in day_horarios:
                            continue
                        horario = horario_aula_curso.horario_dia.horario
                        blocks.append(
                            {
                                "id": horario_aula_curso.pk,
                                "aula": horario_aula_curso.aula_curso.aula,
                                "hora": f"{horario.hora_inicio:%H:%M} - {horario.hora_fin:%H:%M}",
                                "materia_id": getattr(clases.get((horario_aula_curso.pk, current_date)), "materia_curso", None).materia_id
                                if clases.get((horario_aula_curso.pk, current_date))
                                else None,
                            }
                        )
                        clase = clases.get((horario_aula_curso.pk, current_date))
                        materia_id = clase.materia_curso.materia_id if clase else None
                        materia = next((item for item in materias if item.pk == materia_id), None)
                        docente = docentes_by_materia_curso.get(clase.materia_curso_id) if clase else None
                        event_color = materia.color if materia else "#dff1ff"
                        title_parts = [
                            str(horario_aula_curso.aula_curso.aula),
                            getattr(materia, "nombre_corto", None) or getattr(materia, "nombre", "Sin materia"),
                        ]
                        if docente:
                            title_parts.append(docente.nombre)
                        calendar_events.append(
                            {
                                "id": f"{horario_aula_curso.pk}-{current_date.isoformat()}",
                                "horarioId": horario_aula_curso.pk,
                                "fecha": current_date.isoformat(),
                                "title": " · ".join(title_parts),
                                "start": f"{current_date.isoformat()}T{horario.hora_inicio:%H:%M:%S}",
                                "end": f"{current_date.isoformat()}T{horario.hora_fin:%H:%M:%S}",
                                "allDay": False,
                                "className": "materia-event" if materia else "sin-materia-event",
                                "color": event_color,
                                "backgroundColor": event_color,
                                "borderColor": event_color,
                                "textColor": readable_text_color(event_color) if materia else "#7c3aed",
                                "aula": str(horario_aula_curso.aula_curso.aula),
                                "hora": f"{horario.hora_inicio:%H:%M} - {horario.hora_fin:%H:%M}",
                                "materiaId": materia_id or "",
                                "materia": getattr(materia, "nombre", "") if materia else "",
                                "docente": docente.nombre if docente else "",
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
            "rows": rows,
            "calendar_events_json": json.dumps(calendar_events),
            "calendar_default_date": calendar_default_date,
            "selected_curso": selected_curso,
            "selected_curso_periodo": selected_curso_periodo,
            "selected_curso_id": selected_curso_id,
            "can_save": self.request.user.is_superuser
            or self.request.user.has_perm("academico.add_clase")
            or self.request.user.has_perm("academico.change_clase"),
        }


class PlanificacionAcademicaExportView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "academico.view_clase"

    weekday_headers = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]

    def get(self, request):
        export_type = request.GET.get("tipo") or "general"
        rows = self.get_rows()
        workbook = Workbook()
        workbook.remove(workbook.active)

        if export_type == "docente":
            grouped = self.group_rows(rows, lambda row: row["docente"] or "Sin docente")
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

        docentes = {
            item.materia_curso_id: item.partner.nombre
            for item in ProfesorMateriaCurso.objects.select_related("partner", "materia_curso")
        }
        rows = []
        for clase in queryset:
            horario = clase.horario_aula_curso.horario_dia.horario
            materia = clase.materia_curso.materia
            rows.append(
                {
                    "fecha": clase.fecha,
                    "dia": clase.horario_aula_curso.horario_dia.dia.dia,
                    "hora": f"{horario.hora_inicio:%H:%M} - {horario.hora_fin:%H:%M}",
                    "grupo": clase.materia_curso.grupo.nombre,
                    "aula": str(clase.horario_aula_curso.aula_curso.aula),
                    "materia": materia.nombre,
                    "docente": docentes.get(clase.materia_curso_id, ""),
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
            week_matrix = {(row["hora"], row["fecha"].weekday()): row for row in week_rows}
            for time_slot in time_slots:
                time_cell = sheet.cell(row=current_row, column=1, value=time_slot)
                time_cell.font = Font(bold=True, color="FFFFFF")
                time_cell.fill = time_fill
                time_cell.border = border
                time_cell.alignment = center
                for weekday in range(7):
                    cell = sheet.cell(row=current_row, column=weekday + 2)
                    item = week_matrix.get((time_slot, weekday))
                    if item:
                        cell.value = self.schedule_label(item)
                        cell.fill = PatternFill("solid", fgColor=xlsx_color(item["color"]))
                        cell.font = Font(color=xlsx_color(readable_text_color(item["color"])), bold=True)
                    else:
                        cell.value = ""
                        cell.fill = PatternFill("solid", fgColor="FFFFFF")
                    cell.border = border
                    cell.alignment = center
                sheet.row_dimensions[current_row].height = 46
                current_row += 1

            current_row += 2

        if not rows:
            sheet.cell(row=3, column=1, value="Sin horarios registrados.")

        widths = [18, 24, 24, 24, 24, 24, 24, 24]
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
        docentes = (
            Partner.objects.filter(profesor_materia_cursos__isnull=False)
            .annotate(total_asignaciones=Count("profesor_materia_cursos", distinct=True))
            .order_by("nombre")
            .distinct()
        )
        q = request.GET.get("q")
        if q:
            docentes = docentes.filter(Q(nombre__icontains=q) | Q(identificacion__icontains=q))
        return render(
            request,
            self.template_name,
            {
                "title": "Planificacion docente",
                "docentes": docentes,
            },
        )


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

    def get(self, request):
        docente = getattr(request.user, "partner", None)
        if not docente or not docente.es_docente:
            return render(
                request,
                self.template_name,
                {
                    "title": "Mis horarios",
                    "docente": None,
                    "calendar_events_json": json.dumps([]),
                    "calendar_default_date": timezone.localdate().isoformat(),
                    "has_events": False,
                },
            )

        clases = (
            Clase.objects.select_related(
                "materia_curso__materia",
                "materia_curso__grupo",
                "horario_aula_curso__aula_curso__aula",
                "horario_aula_curso__aula_curso__curso",
                "horario_aula_curso__horario_dia__horario",
            )
            .filter(materia_curso__profesor_materia_cursos__partner=docente)
            .order_by("fecha", "horario_aula_curso__horario_dia__horario__hora_inicio")
        )
        calendar_events = []
        calendar_default_date = timezone.localdate().isoformat()
        first_clase = clases.first()
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
                    "className": "materia-event",
                    "backgroundColor": event_color,
                    "borderColor": event_color,
                    "textColor": readable_text_color(event_color),
                    "grupo": grupo.nombre,
                    "aula": str(aula),
                    "materia": materia.nombre,
                    "hora": f"{horario.hora_inicio:%H:%M} - {horario.hora_fin:%H:%M}",
                    "url": str(reverse_lazy("academico:docente_clase_planificar", kwargs={"pk": clase.pk})),
                }
            )

        return render(
            request,
            self.template_name,
            {
                "title": "Mis horarios",
                "docente": docente,
                "calendar_events_json": json.dumps(calendar_events),
                "calendar_default_date": calendar_default_date,
                "has_events": bool(calendar_events),
            },
        )


class DocenteClasePlanificacionView(LoginRequiredMixin, View):
    template_name = "academico/docente_clase_planificacion.html"

    def get_clase(self):
        docente = getattr(self.request.user, "partner", None)
        return get_object_or_404(
            Clase.objects.select_related(
                "materia_curso__materia",
                "materia_curso__grupo",
                "horario_aula_curso__aula_curso__aula",
                "horario_aula_curso__horario_dia__horario",
            ).filter(materia_curso__profesor_materia_cursos__partner=docente),
            pk=self.kwargs["pk"],
        )

    def get(self, request, pk):
        clase = self.get_clase()
        form = DocenteClasePlanificacionForm(instance=clase, clase=clase)
        return render(request, self.template_name, self.get_context(form, clase))

    def post(self, request, pk):
        clase = self.get_clase()
        form = DocenteClasePlanificacionForm(request.POST, request.FILES, instance=clase, clase=clase)
        if form.is_valid():
            with transaction.atomic():
                clase = form.save()
                self.sync_tags(clase.competencias, Competencia, "competencias")
                self.sync_tags(clase.estrategias, Estrategia, "estrategias")
                recurso_ids = self.sync_tags(clase.recursos, Recurso, "recursos")
                self.sync_resource_files(clase, recurso_ids)
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
            messages.success(request, "Clase planificada correctamente.")
            return redirect("academico:docente_horarios")
        return render(request, self.template_name, self.get_context(form, clase))

    def sync_tags(self, relation, model, prefix):
        selected_ids = {
            int(value)
            for value in self.request.POST.getlist(f"{prefix}_existentes")
            if str(value).isdigit()
        }
        for nombre in self.get_new_tag_names(prefix):
            obj, _ = model.objects.get_or_create(nombre=nombre)
            selected_ids.add(obj.pk)
        relation.set(selected_ids)
        return selected_ids

    def sync_resource_files(self, clase, recurso_ids):
        ClaseRecurso.objects.filter(clase=clase).exclude(recurso_id__in=recurso_ids).delete()
        for recurso_id in recurso_ids:
            clase_recurso, _ = ClaseRecurso.objects.get_or_create(clase=clase, recurso_id=recurso_id)
            uploaded = self.request.FILES.get(f"recurso_archivo_{recurso_id}")
            if uploaded:
                clase_recurso.archivo = uploaded
                clase_recurso.save(update_fields=["archivo"])

    def get_new_tag_names(self, prefix):
        try:
            total = int(self.request.POST.get(f"{prefix}-TOTAL_FORMS", 0))
        except (TypeError, ValueError):
            total = 0
        names = []
        for index in range(total):
            name = (self.request.POST.get(f"{prefix}-{index}-nombre") or "").strip()
            delete = self.request.POST.get(f"{prefix}-{index}-DELETE") == "on"
            if name and not delete:
                names.append(name)
        return names

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
        recursos_existing = [
            {
                "obj": recurso,
                "selected": recurso.pk in set(clase.recursos.values_list("id", flat=True)),
                "clase_recurso": clase_recursos_by_id.get(recurso.pk),
            }
            for recurso in Recurso.objects.order_by("nombre")
        ]
        return {
            "title": "Planificar clase",
            "form": form,
            "clase": clase,
            "horario": horario,
            "temas": temas,
            "subtemas_by_tema_json": json.dumps(subtemas_by_tema),
            "tag_groups": [
                {
                    "title": "Competencias",
                    "prefix": "competencias",
                    "existing": Competencia.objects.order_by("nombre"),
                    "selected_ids": set(clase.competencias.values_list("id", flat=True)),
                    "add_label": "Agregar competencia",
                    "placeholder": "Nueva competencia",
                    "revision_note": observaciones.get("competencias", ""),
                    "files_by_id": {},
                },
                {
                    "title": "Estrategias",
                    "prefix": "estrategias",
                    "existing": Estrategia.objects.order_by("nombre"),
                    "selected_ids": set(clase.estrategias.values_list("id", flat=True)),
                    "add_label": "Agregar estrategia",
                    "placeholder": "Nueva estrategia",
                    "revision_note": observaciones.get("estrategias", ""),
                    "files_by_id": {},
                },
                {
                    "title": "Recursos",
                    "prefix": "recursos",
                    "existing": recursos_existing,
                    "selected_ids": set(clase.recursos.values_list("id", flat=True)),
                    "add_label": "Agregar recurso",
                    "placeholder": "Nuevo recurso",
                    "revision_note": observaciones.get("recursos", ""),
                },
            ],
            "clase_recursos_by_id": clase_recursos_by_id,
            "observaciones_revision": observaciones,
            "cancel_url": reverse_lazy("academico:docente_horarios"),
        }


class CoordinacionRevisionPlanificacionesView(CoordinacionRequiredMixin, View):
    template_name = "academico/coordinacion_revision_planificaciones.html"

    def get(self, request):
        estado = request.GET.get("estado", "")
        clases = (
            Clase.objects.select_related(
                "materia_curso__materia",
                "materia_curso__grupo",
                "tema",
                "subtema",
                "horario_aula_curso__aula_curso__aula",
                "horario_aula_curso__horario_dia__horario",
            )
            .prefetch_related("materia_curso__profesor_materia_cursos__partner")
            .order_by("-fecha", "materia_curso__grupo__nombre")
        )
        if estado:
            clases = clases.filter(estado_planificacion=estado)
        q = request.GET.get("q")
        if q:
            clases = clases.filter(
                Q(materia_curso__materia__nombre__icontains=q)
                | Q(materia_curso__grupo__nombre__icontains=q)
                | Q(tema__nombre__icontains=q)
            )
        return render(
            request,
            self.template_name,
            {
                "title": "Revision de planificaciones",
                "clases": clases,
                "estado_choices": Clase.ESTADO_PLANIFICACION_CHOICES,
                "selected_estado": estado,
            },
        )


class CoordinacionRevisionPlanificacionDetalleView(CoordinacionRequiredMixin, View):
    template_name = "academico/coordinacion_revision_planificacion_detalle.html"

    def get_clase(self):
        return get_object_or_404(
            Clase.objects.select_related(
                "materia_curso__materia",
                "materia_curso__grupo",
                "tema",
                "subtema",
                "horario_aula_curso__aula_curso__aula",
                "horario_aula_curso__horario_dia__horario",
            ).prefetch_related("competencias", "estrategias", "recursos", "materia_curso__profesor_materia_cursos__partner"),
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
        clase.revision_tema_ok = request.POST.get("revision_tema_ok") == "on"
        clase.revision_detalle_ok = request.POST.get("revision_detalle_ok") == "on"
        clase.revision_competencias_ok = request.POST.get("revision_competencias_ok") == "on"
        clase.revision_estrategias_ok = request.POST.get("revision_estrategias_ok") == "on"
        clase.revision_recursos_ok = request.POST.get("revision_recursos_ok") == "on"
        section_comments = self.get_section_comments(request)
        if action == "rechazar":
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
            value = request.POST.get(f"observacion_{key}", "").strip()
            if value:
                comments[key] = value
        return comments

    def get_context(self, clase):
        horario = clase.horario_aula_curso.horario_dia.horario
        return {
            "title": "Revisar planificacion",
            "clase": clase,
            "horario": horario,
            "list_url": reverse_lazy("academico:coordinacion_revision_planificaciones"),
        }


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
