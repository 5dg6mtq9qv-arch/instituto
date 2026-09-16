from .menu import permitted_menu_groups, permitted_menu_items
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
    active_view_name = getattr(request.resolver_match, "view_name", "")
    return {
        "security_menu": permitted_menu_items(request.user),
        "security_menu_groups": permitted_menu_groups(request.user, active_view_name),
        "institution_brand": get_institution_brand(),
    }
