from .menu import permitted_menu_items


def security_menu(request):
    return {"security_menu": permitted_menu_items(request.user)}
