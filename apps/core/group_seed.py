from django.apps import apps as django_apps
from django.contrib.auth import get_permission_codename
from django.contrib.auth.models import Group, Permission
from django.db.models.signals import post_migrate
from django.dispatch import receiver


DEFAULT_GROUPS = ("Administrador", "Direccion", "Coordinacion", "Docente", "Director")

DIRECTOR_PERMISSIONS = (
    ("academico", "horarioclase", "add"),
    ("academico", "horarioclase", "change"),
    ("academico", "horarioclase", "view"),
    ("academico", "horarioclase", "view_all"),
    ("academico", "planificacionclase", "change"),
    ("academico", "planificacionclase", "view"),
    ("academico", "planificacionclase", "review"),
    ("academico", "tema", "add"),
)


def permissions_for(app_labels=None, actions=None):
    queryset = Permission.objects.select_related("content_type")
    if app_labels:
        queryset = queryset.filter(content_type__app_label__in=app_labels)
    if actions:
        prefixes = tuple(f"{action}_" for action in actions)
        queryset = [permission for permission in queryset if permission.codename.startswith(prefixes)]
    return queryset


def director_permissions():
    permissions = []
    for app_label, model_name, action in DIRECTOR_PERMISSIONS:
        model = django_apps.get_model(app_label, model_name)
        codename = get_permission_codename(action, model._meta)
        try:
            permissions.append(
                Permission.objects.get(
                    content_type__app_label=app_label,
                    content_type__model=model_name,
                    codename=codename,
                )
            )
        except Permission.DoesNotExist:
            continue
    return permissions


def seed_default_groups():
    groups = {name: Group.objects.get_or_create(name=name)[0] for name in DEFAULT_GROUPS}

    groups["Administrador"].permissions.add(*Permission.objects.all())
    groups["Direccion"].permissions.add(*permissions_for(actions=("view",)))
    groups["Coordinacion"].permissions.add(
        *permissions_for(app_labels=("core", "matricula", "academico"), actions=("add", "change", "view"))
    )
    groups["Docente"].permissions.add(*permissions_for(app_labels=("academico",), actions=("add", "change", "view")))
    groups["Director"].permissions.add(*director_permissions())


@receiver(post_migrate)
def create_default_groups(sender, **kwargs):
    seed_default_groups()
