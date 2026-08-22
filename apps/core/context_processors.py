from .menu import permitted_menu_groups, permitted_menu_items


def security_menu(request):
    active_view_name = getattr(request.resolver_match, "view_name", "")
    return {
        "security_menu": permitted_menu_items(request.user),
        "security_menu_groups": permitted_menu_groups(request.user, active_view_name),
    }
