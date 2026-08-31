MENU_ITEMS = [
    {"label": "Panel", "url_name": "home", "perm": None, "icon": "ri-home-4-line"},
    {
        "label": "Matricular",
        "url_name": "matricula:matricula_proceso",
        "perm": "matricula.add_fichainscripcion",
        "icon": "ri-user-add-line",
    },
    {"label": "Estudiantes", "url_name": "core:estudiante_list", "perm": "core.view_partner", "icon": "ri-graduation-cap-line"},
    {"label": "Representantes", "url_name": "core:representante_list", "perm": "core.view_partner", "icon": "ri-account-circle-line"},
    {
        "label": "Fichas",
        "url_name": "matricula:ficha_list",
        "perm": "matricula.view_fichainscripcion",
        "icon": "ri-file-list-3-line",
    },
    {"label": "Aulas", "url_name": "matricula:aula_list", "perm": "matricula.view_aula", "icon": "ri-door-open-line"},
    {"label": "Cuotas", "url_name": "cartera:cuota_list", "perm": "cartera.view_cuota", "icon": "ri-bill-line"},
    {"label": "Pagos registrados", "url_name": "cartera:pago_list", "perm": "cartera.view_pago", "icon": "ri-bank-card-line"},
    {
        "label": "Cursos academicos",
        "url_name": "academico:curso_list",
        "perm": "academico.view_curso",
        "icon": "ri-calendar-check-line",
    },
    {
        "label": "Grupos",
        "url_name": "core:grupo_list",
        "perm": None,
        "groups": ["Administrador"],
        "icon": "ri-shield-user-line",
    },
    {
        "label": "Usuarios",
        "url_name": "core:usuario_list",
        "perm": None,
        "groups": ["Administrador"],
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
            {"label": "Estudiantes", "url_name": "core:estudiante_list", "perm": "core.view_partner"},
            {"label": "Representantes", "url_name": "core:representante_list", "perm": "core.view_partner"},
        ],
    },
    {
        "label": "Administrativo",
        "icon": "ri-building-4-line",
        "items": [
            {"label": "Docentes", "url_name": "core:docente_list", "perm": None, "groups": ["Director"]},
            {"label": "Usuarios", "url_name": "core:usuario_list", "perm": None, "groups": ["Administrador"]},
            {"label": "Grupos", "url_name": "core:grupo_list", "perm": None, "groups": ["Administrador"]},
        ],
    },
    {
        "label": "Academico",
        "icon": "ri-graduation-cap-line",
        "items": [
            {"label": "Cursos", "url_name": "academico:curso_list", "perm": "academico.view_curso"},
            {"label": "Aulas", "url_name": "academico:aula_list", "perm": "academico.view_aula"},
            {"label": "Materias", "url_name": "academico:materia_list", "perm": "academico.view_materia"},
            {"label": "Periodos", "url_name": "academico:periodo_list", "perm": "academico.view_periodo"},
            {"label": "Planificacion academica", "url_name": "academico:planificacion_academica", "perm": "academico.view_clase"},
            {"label": "Planificacion docente", "url_name": "academico:planificacion_docente", "perm": "academico.view_profesormateriacurso"},
            {"label": "Estudiantes por grupo", "url_name": "academico:grupo_estudiantes", "perm": "academico.view_grupoestudiante"},
        ],
    },
    {
        "label": "Coordinacion",
        "icon": "ri-stack-line",
        "items": [
            {
                "label": "Temas",
                "url_name": "academico:coordinacion_planificacion_list",
                "perm": None,
                "groups": ["Coordinacion", "Direccion", "Director"],
            },
            {
                "label": "Revision docente",
                "url_name": "academico:coordinacion_revision_planificaciones",
                "perm": None,
                "groups": ["Coordinacion", "Direccion", "Director"],
            },
            {
                "label": "Revision asistencia",
                "url_name": "academico:coordinacion_revision_asistencia",
                "perm": None,
                "groups": ["Coordinacion", "Direccion", "Director"],
            },
            {
                "label": "Asistencia alumno",
                "url_name": "academico:coordinacion_reporte_asistencia_alumno",
                "perm": None,
                "groups": ["Coordinacion", "Direccion", "Director"],
            },
        ],
    },
    {
        "label": "Docente",
        "icon": "ri-user-star-line",
        "items": [
            {"label": "Mis planificaciones", "url_name": "academico:docente_horarios", "perm": None, "groups": ["Docente"]},
            {"label": "Mi calendario", "url_name": "academico:docente_calendario", "perm": None, "groups": ["Docente"]},
        ],
    },
    {
        "label": "Cartera",
        "icon": "ri-money-dollar-circle-line",
        "items": [
            {"label": "Cobros por alumno", "url_name": "cartera:alumno_cartera_list", "perm": "cartera.view_cuota"},
            {"label": "Cuotas", "url_name": "cartera:cuota_list", "perm": "cartera.view_cuota"},
            {"label": "Pagos registrados", "url_name": "cartera:pago_list", "perm": "cartera.view_pago"},
            {"label": "Planes de pago", "url_name": "cartera:plan_pago_list", "perm": "cartera.view_planpago"},
            {"label": "Formas de pago", "url_name": "cartera:forma_pago_list", "perm": "cartera.view_formapago"},
        ],
    },
]


def user_can_see_menu_item(user, item):
    if item.get("superuser_only"):
        return user.is_superuser
    groups = item.get("groups")
    if groups and not (user.is_superuser or user.groups.filter(name__in=groups).exists()):
        return False
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
