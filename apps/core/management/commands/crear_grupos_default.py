from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand

from apps.core.group_seed import DEFAULT_GROUPS, seed_default_groups


class Command(BaseCommand):
    help = "Crea o actualiza los grupos y permisos por defecto del sistema."

    def handle(self, *args, **options):
        seed_default_groups()
        for name in DEFAULT_GROUPS:
            group = Group.objects.get(name=name)
            self.stdout.write(f"{group.name}: {group.permissions.count()} permisos")
        self.stdout.write(self.style.SUCCESS("Grupos por defecto creados/actualizados."))
