from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

from apps.academico.models import Aula as AulaAcademica, Clase
from apps.cartera.models import Cuota, Pago
from apps.core.models import Empresa, Partner
from apps.matricula.models import Aula, Curso, FichaInscripcion, PeriodoAcademico


@login_required
def home(request):
    User = get_user_model()
    user = request.user
    today = timezone.localdate()
    institution = Empresa.objects.first()
    institution_name = institution.nombre_display() if institution else "Instituto"

    def can(perm):
        return user.is_superuser or user.has_perm(perm)

    def has_group(*names):
        return user.is_superuser or user.groups.filter(name__in=names).exists()

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

    def director_can_manage_docentes():
        return user.is_superuser or user.groups.filter(name="Director").exists()

    def metric(label, value, icon, accent, helper="", url_name=None, url=""):
        return {
            "label": label,
            "value": value,
            "icon": icon,
            "accent": accent,
            "helper": helper,
            "url": url or (reverse(url_name) if url_name else ""),
        }

    def action(label, url_name, icon, variant="primary", url=""):
        return {
            "label": label,
            "url": url or reverse(url_name),
            "icon": icon,
            "variant": variant,
        }

    def base_clases_queryset():
        return Clase.objects.select_related(
            "materia_curso__materia",
            "materia_curso__grupo",
            "tema",
            "horario_aula_curso__aula_curso__aula",
            "horario_aula_curso__horario_dia__horario",
        ).order_by("fecha", "horario_aula_curso__horario_dia__horario__hora_inicio")

    def clase_item(clase, url_name, icon, accent, badge=None, url=""):
        horario = clase.horario_aula_curso.horario_dia.horario
        materia = clase.materia_curso.materia
        grupo = clase.materia_curso.grupo
        return {
            "title": f"{materia.nombre_corto or materia.nombre} - {grupo.nombre}",
            "meta": f"{clase.fecha:%d/%m/%Y} · {horario.hora_inicio:%H:%M} - {horario.hora_fin:%H:%M} · {clase.horario_aula_curso.aula_curso.aula}",
            "note": str(clase.tema) if clase.tema else "",
            "badge": badge or clase.get_estado_planificacion_display(),
            "url": url or reverse(url_name, args=[clase.pk]),
            "icon": icon,
            "accent": accent,
        }

    def cuota_item(cuota):
        return {
            "title": f"Cuota {cuota.numero}",
            "meta": f"Vence {cuota.fecha_pago_debito:%d/%m/%Y} · saldo {cuota.saldo():.2f}",
            "note": str(cuota.plan_pago.ficha_inscripcion.estudiante),
            "badge": cuota.get_estado_display(),
            "url": reverse("cartera:cuota_list"),
            "icon": "ri-bill-line",
            "accent": "danger",
        }

    def priority_section(title, description, items, empty_text, icon, accent="primary"):
        return {
            "title": title,
            "description": description,
            "items": items,
            "empty_text": empty_text,
            "icon": icon,
            "accent": accent,
        }

    def institutional_metrics():
        return [
            metric("Empresas", Empresa.objects.count(), "ri-building-4-line", "warning", "Configuracion institucional", "core:empresa_list"),
            metric("Estudiantes", Partner.objects.filter(es_estudiante=True).count(), "ri-graduation-cap-line", "blue", "Matriculados registrados", "core:estudiante_list"),
            metric("Fichas", FichaInscripcion.objects.count(), "ri-file-list-3-line", "purple", "Inscripciones registradas", "matricula:ficha_list"),
            metric("Cuotas pendientes", Cuota.objects.filter(estado__in=["pendiente", "parcial", "vencida"]).count(), "ri-bill-line", "primary", "Valores por cobrar", "cartera:cuota_list"),
        ]

    def build_docente_dashboard(docente):
        clases = base_clases_queryset().filter(materia_curso__profesor_materia_cursos__partner=docente).distinct()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        por_atender = clases.filter(estado_planificacion__in=["pendiente", "rechazada"])
        atrasadas = por_atender.filter(fecha__lt=today)
        semana = clases.filter(fecha__range=(week_start, week_end))
        return {
            "profile": {
                "role": "docente",
                "eyebrow": "Panel docente",
                "title": docente.nombre,
                "subtitle": "Resumen de tus clases, planificaciones enviadas y pendientes por corregir.",
            },
            "metrics": [
                metric("Mis clases", clases.count(), "ri-calendar-check-line", "primary", "Total de clases asignadas", "academico:docente_calendario"),
                metric("Por planificar", por_atender.count(), "ri-edit-2-line", "warning", f"{atrasadas.count()} atrasada(s)", "academico:docente_horarios"),
                metric("En revision", clases.filter(estado_planificacion="revision").count(), "ri-search-eye-line", "blue", "Esperando respuesta de coordinacion", "academico:docente_horarios"),
                metric("Aprobadas", clases.filter(estado_planificacion="aprobada").count(), "ri-checkbox-circle-line", "success", "Planificaciones validadas", "academico:docente_horarios"),
            ],
            "actions": [
                action("Planificaciones", "academico:docente_horarios", "ri-task-line"),
                action("Calendario", "academico:docente_calendario", "ri-calendar-schedule-line", "secondary"),
            ],
            "priority_sections": [
                priority_section(
                    "Por atender",
                    "Clases pendientes o devueltas para corregir.",
                    [clase_item(clase, "academico:docente_clase_planificar", "ri-edit-2-line", "warning") for clase in por_atender[:5]],
                    "No tienes planificaciones pendientes.",
                    "ri-inbox-unarchive-line",
                    "warning",
                ),
                priority_section(
                    "Esta semana",
                    f"Clases del {week_start:%d/%m} al {week_end:%d/%m}.",
                    [clase_item(clase, "academico:docente_clase_planificar", "ri-calendar-line", "primary") for clase in semana[:5]],
                    "No tienes clases esta semana.",
                    "ri-calendar-week-line",
                    "primary",
                ),
                priority_section(
                    "Observadas",
                    "Planificaciones rechazadas que necesitan ajuste.",
                    [
                        clase_item(clase, "academico:docente_clase_planificar", "ri-error-warning-line", "danger")
                        for clase in clases.filter(estado_planificacion="rechazada")[:5]
                    ],
                    "No tienes observaciones pendientes.",
                    "ri-error-warning-line",
                    "danger",
                ),
            ],
        }

    def build_coordinacion_dashboard():
        clases = base_clases_queryset()
        revisiones = clases.filter(estado_planificacion="revision")
        atrasadas = clases.filter(fecha__lt=today, estado_planificacion__in=["pendiente", "rechazada"])
        sin_docente = clases.filter(
            fecha__gte=today,
            materia_curso__profesor_materia_cursos__isnull=True,
        ).distinct()
        asignacion_base_url = reverse("academico:planificacion_docente")
        return {
            "profile": {
                "role": "coordinacion",
                "eyebrow": "Panel de coordinacion",
                "title": institution_name or "Coordinacion academica",
                "subtitle": "Seguimiento de planificaciones enviadas, atrasos y clases sin docente asignado.",
            },
            "metrics": [
                metric("Por revisar", revisiones.count(), "ri-search-eye-line", "blue", "Planificaciones enviadas", "academico:coordinacion_revision_planificaciones"),
                metric("Atrasadas", atrasadas.count(), "ri-alarm-warning-line", "danger", "Pendientes o rechazadas fuera de fecha", "academico:coordinacion_revision_planificaciones"),
                metric("Observadas", clases.filter(estado_planificacion="rechazada").count(), "ri-error-warning-line", "warning", "Devueltas al docente", "academico:coordinacion_revision_planificaciones"),
                metric("Sin docente", sin_docente.count(), "ri-user-unfollow-line", "primary", "Clases futuras sin asignacion", "academico:planificacion_docente"),
            ],
            "actions": [
                action("Revision docente", "academico:coordinacion_revision_planificaciones", "ri-search-eye-line"),
                action("Temas", "academico:coordinacion_planificacion_list", "ri-stack-line", "secondary"),
                action("Asignar docentes", "academico:planificacion_docente", "ri-user-add-line", "secondary"),
            ],
            "priority_sections": [
                priority_section(
                    "Enviadas a revision",
                    "Clases que esperan decision de coordinacion.",
                    [clase_item(clase, "academico:coordinacion_revision_planificacion_detalle", "ri-search-eye-line", "blue") for clase in revisiones[:5]],
                    "No hay planificaciones enviadas.",
                    "ri-search-eye-line",
                    "blue",
                ),
                priority_section(
                    "Atrasadas",
                    "Planificaciones que no llegaron a tiempo.",
                    [clase_item(clase, "academico:coordinacion_revision_planificacion_detalle", "ri-alarm-warning-line", "danger") for clase in atrasadas[:5]],
                    "No hay atrasos de planificacion.",
                    "ri-alarm-warning-line",
                    "danger",
                ),
                priority_section(
                    "Sin docente",
                    "Clases futuras que aun necesitan asignacion.",
                    [
                        clase_item(
                            clase,
                            "academico:coordinacion_revision_planificacion_detalle",
                            "ri-user-unfollow-line",
                            "warning",
                            "Sin docente",
                            f"{asignacion_base_url}?grupo={clase.materia_curso.grupo_id}",
                        )
                        for clase in sin_docente[:5]
                    ],
                    "No hay clases futuras sin docente.",
                    "ri-user-unfollow-line",
                    "warning",
                ),
            ],
        }

    def build_director_dashboard():
        clases = base_clases_queryset()
        revisiones = clases.filter(estado_planificacion="revision")
        sin_docente = clases.filter(
            fecha__gte=today,
            fecha__lte=today + timedelta(days=30),
            materia_curso__profesor_materia_cursos__isnull=True,
        ).distinct()
        cuotas_pendientes = Cuota.objects.select_related("plan_pago__ficha_inscripcion__estudiante").filter(
            estado__in=["pendiente", "parcial", "vencida"]
        )
        cuotas_vencidas = cuotas_pendientes.filter(Q(estado="vencida") | Q(fecha_pago_debito__lt=today))
        return {
            "profile": {
                "role": "direccion",
                "eyebrow": "Panel directivo",
                "title": institution_name or "Direccion institucional",
                "subtitle": "Pendientes academicos, financieros y operativos que requieren seguimiento.",
            },
            "metrics": [
                metric("Sin docente", sin_docente.count(), "ri-user-unfollow-line", "warning", "Proximos 30 dias", "academico:planificacion_docente"),
                metric("Por revisar", revisiones.count(), "ri-search-eye-line", "blue", "Planificaciones enviadas", "academico:coordinacion_revision_planificaciones"),
                metric("Cuotas pendientes", cuotas_pendientes.count(), "ri-bill-line", "danger", f"{cuotas_vencidas.count()} vencida(s)", "cartera:cuota_list"),
                metric("Clases futuras", clases.filter(fecha__gte=today).count(), "ri-calendar-check-line", "primary", "Planificacion academica activa", "academico:planificacion_academica"),
            ],
            "actions": [
                action("Planificacion academica", "academico:planificacion_academica", "ri-calendar-check-line"),
                action("Asignar docentes", "academico:planificacion_docente", "ri-user-add-line", "secondary"),
                action("Revision docente", "academico:coordinacion_revision_planificaciones", "ri-search-eye-line", "secondary"),
                action("Cartera", "cartera:cuota_list", "ri-bill-line", "secondary"),
            ],
            "priority_sections": [
                priority_section(
                    "Clases sin docente",
                    "Asignaciones pendientes en los proximos 30 dias.",
                    [
                        clase_item(
                            clase,
                            "academico:coordinacion_revision_planificacion_detalle",
                            "ri-user-unfollow-line",
                            "warning",
                            "Sin docente",
                            f"{reverse('academico:planificacion_docente')}?grupo={clase.materia_curso.grupo_id}",
                        )
                        for clase in sin_docente[:5]
                    ],
                    "No hay clases proximas sin docente.",
                    "ri-user-unfollow-line",
                    "warning",
                ),
                priority_section(
                    "Revision docente",
                    "Planificaciones listas para aprobar u observar.",
                    [clase_item(clase, "academico:coordinacion_revision_planificacion_detalle", "ri-search-eye-line", "blue") for clase in revisiones[:5]],
                    "No hay planificaciones por revisar.",
                    "ri-search-eye-line",
                    "blue",
                ),
                priority_section(
                    "Cartera pendiente",
                    "Cuotas pendientes o vencidas.",
                    [cuota_item(cuota) for cuota in cuotas_pendientes[:5]],
                    "No hay cuotas pendientes.",
                    "ri-bill-line",
                    "danger",
                ),
            ],
        }

    def build_institutional_dashboard():
        return {
            "profile": {
                "role": "institucional",
                "eyebrow": "Panel institucional",
                "title": institution_name or "Instituto",
                "subtitle": "Resumen general de matriculas, cartera y modulos administrativos.",
            },
            "metrics": institutional_metrics(),
            "actions": [],
            "priority_sections": [],
        }

    dashboard_sections = [
        {
            "slug": "administrativo",
            "title": "Administrativo",
            "description": "Estructura base, docentes y accesos del sistema.",
            "cards": visible_cards(
                [
                    card("Aulas", "Listado, jornada, horario y capacidad.", Aula.objects.count(), "matricula:aula_list", "ri-door-open-line", "primary", "matricula.view_aula", "matricula:aula_nueva"),
                    card("Periodos", "Ciclos activos, fechas y regimen.", PeriodoAcademico.objects.count(), "matricula:periodo_list", "ri-calendar-2-line", "info", "matricula.view_periodoacademico", "matricula:periodo_nuevo"),
                    card("Cursos", "Ofertas, carreras y universidades.", Curso.objects.count(), "matricula:curso_list", "ri-graduation-cap-line", "warning", "matricula.view_curso", "matricula:curso_nuevo"),
                    card("Docentes", "Perfiles docentes para planificacion.", Partner.objects.filter(es_docente=True).count(), "core:docente_list", "ri-user-star-line", "purple", None, "core:docente_nuevo", "Nuevo docente") if director_can_manage_docentes() else None,
                    card("Usuarios", "Accesos y grupos del sistema.", User.objects.count(), "core:usuario_list", "ri-user-settings-line", "blue", None, "core:usuario_nuevo") if user.is_superuser else None,
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
                    card("Matriculados", "Fichas activas por periodo y aula.", FichaInscripcion.objects.filter(estado="activa").count(), "matricula:ficha_list", "ri-file-list-3-line", "success", "matricula.view_fichainscripcion", "matricula:matricula_proceso", "Matricular"),
                    card("Estudiantes", "Creados desde el proceso de matricula.", Partner.objects.filter(es_estudiante=True).count(), "core:estudiante_list", "ri-graduation-cap-line", "info", "core.view_partner"),
                    card("Representantes", "Contactos y responsables de pago.", Partner.objects.filter(es_representante=True).count(), "core:representante_list", "ri-account-circle-line", "warning", "core.view_partner"),
                ]
            ),
        },
        {
            "slug": "educativo",
            "title": "Academico",
            "description": "Distribucion de cursos, aulas, grupos y horarios.",
            "cards": visible_cards(
                [
                    card("Aulas", "Crear y editar aulas academicas.", AulaAcademica.objects.count(), "academico:aula_list", "ri-door-open-line", "primary", "academico.view_aula", "academico:aula_nueva"),
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
                ]
            ),
        },
    ]
    docente = getattr(user, "partner", None)
    is_docente = bool(docente and docente.es_docente)
    if has_group("Direccion", "Director"):
        role_dashboard = build_director_dashboard()
    elif has_group("Coordinacion"):
        role_dashboard = build_coordinacion_dashboard()
    elif is_docente:
        role_dashboard = build_docente_dashboard(docente)
    else:
        role_dashboard = build_institutional_dashboard()

    context = {
        "dashboard_profile": role_dashboard["profile"],
        "metrics": role_dashboard["metrics"],
        "dashboard_actions": role_dashboard["actions"],
        "priority_sections": role_dashboard["priority_sections"],
        "dashboard_sections": [section for section in dashboard_sections if section["cards"]],
        "institution": institution,
        "active_period": PeriodoAcademico.objects.filter(estado="activo").first(),
    }
    return render(request, "dashboard/home.html", context)
