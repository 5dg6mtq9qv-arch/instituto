import calendar as calendar_module
import json
from datetime import date, timedelta
from urllib.parse import urlencode

from django.urls import reverse_lazy
from django.db.models import Q
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View

from apps.core.models import Empresa
from apps.core.web_views import InstitutoCreateView, InstitutoListView, InstitutoUpdateView

from .forms import (
    AsignaturaForm,
    AulaForm,
    BancoPreguntaForm,
    CursoForm,
    HorarioAsignacionBaseForm,
    HorarioAsignacionFormSet,
    HorarioClaseForm,
    PlanificacionClaseForm,
    PreguntaForm,
    TemaForm,
    TemarioForm,
)
from .models import Asignatura, Aula, BancoPregunta, Curso, HorarioClase, PlanificacionClase, Pregunta, Tema, Temario


def can_view_all_horarios(user):
    return user.is_superuser or user.groups.filter(name="Director").exists() or user.has_perm("academico.view_all_horarioclase")


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
