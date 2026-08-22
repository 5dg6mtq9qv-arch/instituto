MENU_ITEMS = [
    {"label": "Panel", "url_name": "home", "perm": None, "icon": "ri-home-4-line"},
    {
        "label": "Matricular",
        "url_name": "matricula:matricula_proceso",
        "perm": "matricula.add_fichainscripcion",
        "icon": "ri-user-add-line",
    },
    {"label": "Personas", "url_name": "core:partner_list", "perm": "core.view_partner", "icon": "ri-team-line"},
    {
        "label": "Fichas",
        "url_name": "matricula:ficha_list",
        "perm": "matricula.view_fichainscripcion",
        "icon": "ri-file-list-3-line",
    },
    {"label": "Aulas", "url_name": "matricula:aula_list", "perm": "matricula.view_aula", "icon": "ri-door-open-line"},
    {"label": "Cuotas", "url_name": "cartera:cuota_list", "perm": "cartera.view_cuota", "icon": "ri-bill-line"},
    {"label": "Pagos", "url_name": "cartera:pago_list", "perm": "cartera.view_pago", "icon": "ri-bank-card-line"},
    {
        "label": "Planificacion",
        "url_name": "academico:planificacion_list",
        "perm": "academico.view_planificacionclase",
        "icon": "ri-calendar-check-line",
    },
    {
        "label": "Horarios",
        "url_name": "academico:horario_list",
        "perm": "academico.view_horarioclase",
        "icon": "ri-calendar-schedule-line",
    },
    {
        "label": "Preguntas",
        "url_name": "academico:pregunta_list",
        "perm": "academico.view_pregunta",
        "icon": "ri-question-answer-line",
    },
    {"label": "Grupos", "url_name": "core:grupo_list", "perm": "auth.view_group", "icon": "ri-shield-user-line"},
    {
        "label": "Usuarios",
        "url_name": "core:usuario_list",
        "perm": "auth.view_user",
        "superuser_only": True,
        "icon": "ri-user-settings-line",
    },
]

MENU_GROUPS = [
    {
        "label": "Dashboard",
        "icon": "ri-dashboard-line",
        "items": [
            {"label": "Panel", "url_name": "home", "perm": None},
        ],
    },
    {
        "label": "Matriculas",
        "icon": "ri-user-add-line",
        "items": [
            {"label": "Matricular", "url_name": "matricula:matricula_proceso", "perm": "matricula.add_fichainscripcion"},
            {"label": "Fichas", "url_name": "matricula:ficha_list", "perm": "matricula.view_fichainscripcion"},
            {"label": "Nueva ficha", "url_name": "matricula:ficha_nueva", "perm": "matricula.add_fichainscripcion"},
            {"label": "Personas", "url_name": "core:partner_list", "perm": "core.view_partner"},
            {"label": "Nueva persona", "url_name": "core:partner_nuevo", "perm": "core.add_partner"},
        ],
    },
    {
        "label": "Administrativo",
        "icon": "ri-building-4-line",
        "items": [
            {"label": "Aulas", "url_name": "matricula:aula_list", "perm": "matricula.view_aula"},
            {"label": "Nueva aula", "url_name": "matricula:aula_nueva", "perm": "matricula.add_aula"},
            {"label": "Periodos", "url_name": "matricula:periodo_list", "perm": "matricula.view_periodoacademico"},
            {"label": "Cursos", "url_name": "matricula:curso_list", "perm": "matricula.view_curso"},
            {"label": "Usuarios", "url_name": "core:usuario_list", "perm": "auth.view_user", "superuser_only": True},
            {"label": "Grupos", "url_name": "core:grupo_list", "perm": "auth.view_group"},
        ],
    },
    {
        "label": "Educativo",
        "icon": "ri-graduation-cap-line",
        "items": [
            {"label": "Horarios", "url_name": "academico:horario_list", "perm": "academico.view_horarioclase"},
            {"label": "Calendario", "url_name": "academico:horario_calendario", "perm": "academico.view_horarioclase"},
            {"label": "Asignar horarios", "url_name": "academico:horario_asignacion", "perm": "academico.add_horarioclase"},
            {"label": "Nuevo horario", "url_name": "academico:horario_nuevo", "perm": "academico.add_horarioclase"},
            {"label": "Asignaturas", "url_name": "academico:asignatura_list", "perm": "academico.view_asignatura"},
            {"label": "Temarios", "url_name": "academico:temario_list", "perm": "academico.view_temario"},
            {"label": "Temas", "url_name": "academico:tema_list", "perm": "academico.view_tema"},
            {"label": "Planificaciones", "url_name": "academico:planificacion_list", "perm": "academico.view_planificacionclase"},
            {"label": "Preguntas", "url_name": "academico:pregunta_list", "perm": "academico.view_pregunta"},
        ],
    },
    {
        "label": "Cartera",
        "icon": "ri-money-dollar-circle-line",
        "items": [
            {"label": "Cuotas", "url_name": "cartera:cuota_list", "perm": "cartera.view_cuota"},
            {"label": "Pagos", "url_name": "cartera:pago_list", "perm": "cartera.view_pago"},
            {"label": "Planes de pago", "url_name": "cartera:plan_pago_list", "perm": "cartera.view_planpago"},
            {"label": "Formas de pago", "url_name": "cartera:forma_pago_list", "perm": "cartera.view_formapago"},
        ],
    },
]


def user_can_see_menu_item(user, item):
    if item.get("superuser_only"):
        return user.is_superuser
    perm = item.get("perm")
    return user.is_superuser or not perm or user.has_perm(perm)


def permitted_menu_items(user):
    if not user.is_authenticated:
        return []
    return [item for item in MENU_ITEMS if user_can_see_menu_item(user, item)]


def permitted_menu_groups(user, active_view_name=""):
    if not user.is_authenticated:
        return []
    groups = []
    for group in MENU_GROUPS:
        children = []
        group_is_active = False
        for item in group["items"]:
            if not user_can_see_menu_item(user, item):
                continue
            item = {**item, "active": item["url_name"] == active_view_name}
            group_is_active = group_is_active or item["active"]
            children.append(item)
        if children:
            groups.append(
                {
                    "label": group["label"],
                    "icon": group["icon"],
                    "items": children,
                    "active": group_is_active,
                }
            )
    return groups
