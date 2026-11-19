from .menu import _get_user_group_names, permitted_menu_groups, permitted_menu_items
from .models import Empresa


def get_institution_brand():
    institution = Empresa.objects.filter(activa=True).order_by("pk").first()
    if institution is None:
        institution = Empresa.objects.order_by("pk").first()
    logo_url = ""
    if institution and institution.logo:
        try:
            logo_url = institution.logo.url
        except (ValueError, OSError):
            logo_url = ""
    name = institution.nombre_display() if institution else ""
    return {
        "institution": institution,
        "name": name or "Instituto",
        "logo_url": logo_url,
    }


def security_menu(request):
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {
            "security_menu": [],
            "security_menu_groups": [],
            "institution_brand": get_institution_brand(),
        }
    active_view_name = getattr(request.resolver_match, "view_name", "")
    user_group_names = _get_user_group_names(user)
    return {
        "security_menu": permitted_menu_items(user, user_group_names=user_group_names),
        "security_menu_groups": permitted_menu_groups(
            user,
            active_view_name=active_view_name,
            user_group_names=user_group_names,
        ),
        "institution_brand": get_institution_brand(),
    }
