from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.urls import reverse

from apps.academico.models import Asignatura, BancoPregunta, HorarioClase, PlanificacionClase, Pregunta, Tema, Temario
from apps.cartera.models import Cuota, Pago
from apps.core.models import Empresa, Partner
from apps.matricula.models import Aula, Curso, FichaInscripcion, PeriodoAcademico


@login_required
def home(request):
    User = get_user_model()
    user = request.user

    def can(perm):
        return user.is_superuser or user.has_perm(perm)

    def card(title, description, count, url_name, icon, accent, perm=None, action_url_name=None, action_label="Nuevo"):
        if perm and not can(perm):
            return None
        return {
            "title": title,
            "description": description,
            "count": count,
            "url": reverse(url_name),
            "icon": icon,
            "accent": accent,
            "action_url": reverse(action_url_name) if action_url_name and (not perm or can(perm.replace("view_", "add_"))) else "",
            "action_label": action_label,
        }

    def visible_cards(cards):
        return [item for item in cards if item]

    metrics = [
        {"label": "Empresas", "value": Empresa.objects.count(), "accent": "green"},
        {"label": "Estudiantes", "value": Partner.objects.filter(es_estudiante=True).count(), "accent": "blue"},
        {"label": "Fichas", "value": FichaInscripcion.objects.count(), "accent": "yellow"},
        {"label": "Cuotas pendientes", "value": Cuota.objects.exclude(estado="pagada").count(), "accent": "red"},
    ]

    dashboard_sections = [
        {
            "slug": "administrativo",
            "title": "Administrativo",
            "description": "Estructura base: periodos, aulas, personas y usuarios.",
            "cards": visible_cards(
                [
                    card("Aulas", "Listado, jornada, horario y capacidad.", Aula.objects.count(), "matricula:aula_list", "ri-door-open-line", "primary", "matricula.view_aula", "matricula:aula_nueva"),
                    card("Periodos", "Ciclos activos, fechas y regimen.", PeriodoAcademico.objects.count(), "matricula:periodo_list", "ri-calendar-2-line", "info", "matricula.view_periodoacademico", "matricula:periodo_nuevo"),
                    card("Cursos", "Ofertas, carreras y universidades.", Curso.objects.count(), "matricula:curso_list", "ri-graduation-cap-line", "warning", "matricula.view_curso", "matricula:curso_nuevo"),
                    card("Personas", "Estudiantes, representantes y docentes.", Partner.objects.count(), "core:partner_list", "ri-team-line", "purple", "core.view_partner", "core:partner_nuevo"),
                    card("Usuarios", "Accesos y grupos del sistema.", User.objects.count(), "core:usuario_list", "ri-user-settings-line", "blue", "auth.view_user", "core:usuario_nuevo"),
                ]
            ),
        },
        {
            "slug": "matriculas",
            "title": "Matriculas",
            "description": "Captacion, fichas, matriculados y estado financiero inicial.",
            "cards": visible_cards(
                [
                    card("Matricular", "Crear estudiante, representante, ficha y cuotas.", FichaInscripcion.objects.filter(estado="borrador").count(), "matricula:matricula_proceso", "ri-user-add-line", "primary", "matricula.add_fichainscripcion", "matricula:matricula_proceso", "Iniciar"),
                    card("Matriculados", "Fichas activas por periodo y aula.", FichaInscripcion.objects.filter(estado="activa").count(), "matricula:ficha_list", "ri-file-list-3-line", "success", "matricula.view_fichainscripcion", "matricula:ficha_nueva"),
                    card("Estudiantes", "Personas marcadas como estudiantes.", Partner.objects.filter(es_estudiante=True).count(), "core:partner_list", "ri-graduation-cap-line", "info", "core.view_partner", "core:partner_nuevo"),
                    card("Representantes", "Contactos y responsables de pago.", Partner.objects.filter(es_representante=True).count(), "core:partner_list", "ri-account-circle-line", "warning", "core.view_partner", "core:partner_nuevo"),
                ]
            ),
        },
        {
            "slug": "educativo",
            "title": "Educativo",
            "description": "Materias, horarios, docentes, temarios y planificacion.",
            "cards": visible_cards(
                [
                    card("Horarios", "Clases por aula, fecha, hora y docente.", HorarioClase.objects.count(), "academico:horario_list", "ri-calendar-schedule-line", "primary", "academico.view_horarioclase", "academico:horario_nuevo"),
                    card("Asignaturas", "Materias usadas en horarios y temarios.", Asignatura.objects.count(), "academico:asignatura_list", "ri-book-open-line", "info", "academico.view_asignatura", "academico:asignatura_nueva"),
                    card("Temarios", "Plan curricular por periodo y asignatura.", Temario.objects.count(), "academico:temario_list", "ri-list-check-3", "purple", "academico.view_temario", "academico:temario_nuevo"),
                    card("Planificaciones", "Detalle pedagogico preparado por docentes.", PlanificacionClase.objects.count(), "academico:planificacion_list", "ri-file-edit-line", "warning", "academico.view_planificacionclase", "academico:planificacion_nueva"),
                    card("Preguntas", "Banco de preguntas y simuladores.", Pregunta.objects.count(), "academico:pregunta_list", "ri-question-answer-line", "success", "academico.view_pregunta", "academico:pregunta_nueva"),
                ]
            ),
        },
        {
            "title": "Cartera",
            "slug": "cartera",
            "description": "Cuotas, pagos y seguimiento de saldos.",
            "cards": visible_cards(
                [
                    card("Cuotas pendientes", "Valores por cobrar y vencimientos.", Cuota.objects.exclude(estado="pagada").count(), "cartera:cuota_list", "ri-bill-line", "danger", "cartera.view_cuota", "cartera:cuota_nueva"),
                    card("Pagos", "Abonos y comprobantes registrados.", Pago.objects.count(), "cartera:pago_list", "ri-bank-card-line", "success", "cartera.view_pago", "cartera:pago_nuevo"),
                    card("Bancos", "Bancos de preguntas ligados al proceso.", BancoPregunta.objects.count(), "academico:banco_list", "ri-database-2-line", "info", "academico.view_bancopregunta", "academico:banco_nuevo"),
                ]
            ),
        },
    ]

    context = {
        "metrics": metrics,
        "dashboard_sections": [section for section in dashboard_sections if section["cards"]],
        "institution": Empresa.objects.first(),
        "active_period": PeriodoAcademico.objects.filter(estado="activo").first(),
    }
    return render(request, "dashboard/home.html", context)
