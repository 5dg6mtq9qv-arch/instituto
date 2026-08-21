MENU_ITEMS = [
    {"label": "Panel", "url_name": "home", "perm": None},
    {"label": "Matricular", "url_name": "matricula:matricula_proceso", "perm": "matricula.add_fichainscripcion"},
    {"label": "Personas", "url_name": "core:partner_list", "perm": "core.view_partner"},
    {"label": "Fichas", "url_name": "matricula:ficha_list", "perm": "matricula.view_fichainscripcion"},
    {"label": "Aulas", "url_name": "matricula:aula_list", "perm": "matricula.view_aula"},
    {"label": "Cuotas", "url_name": "cartera:cuota_list", "perm": "cartera.view_cuota"},
    {"label": "Pagos", "url_name": "cartera:pago_list", "perm": "cartera.view_pago"},
    {"label": "Planificacion", "url_name": "academico:planificacion_list", "perm": "academico.view_planificacionclase"},
    {"label": "Preguntas", "url_name": "academico:pregunta_list", "perm": "academico.view_pregunta"},
    {"label": "Grupos", "url_name": "core:grupo_list", "perm": "auth.view_group"},
]


def user_can_see_menu_item(user, item):
    perm = item.get("perm")
    return user.is_superuser or not perm or user.has_perm(perm)


def permitted_menu_items(user):
    if not user.is_authenticated:
        return []
    return [item for item in MENU_ITEMS if user_can_see_menu_item(user, item)]
