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


def user_can_see_menu_item(user, item):
    if item.get("superuser_only"):
        return user.is_superuser
    perm = item.get("perm")
    return user.is_superuser or not perm or user.has_perm(perm)


def permitted_menu_items(user):
    if not user.is_authenticated:
        return []
    return [item for item in MENU_ITEMS if user_can_see_menu_item(user, item)]
