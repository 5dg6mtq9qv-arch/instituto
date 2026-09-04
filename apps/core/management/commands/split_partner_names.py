from django.core.management.base import BaseCommand

from apps.core.models import Partner


def split_full_name(value):
    parts = str(value or "").split()
    if len(parts) >= 4:
        return " ".join(parts[:-2]), " ".join(parts[-2:])
    if len(parts) >= 2:
        return " ".join(parts[:-1]), parts[-1]
    return str(value or "").strip(), ""


class Command(BaseCommand):
    help = "Separa nombres completos existentes de Partner en nombre y apellido."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Guarda los cambios. Sin esto solo muestra una vista previa.")
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Recalcula tambien registros que ya tienen apellido.",
        )

    def handle(self, *args, **options):
        queryset = Partner.objects.all().order_by("id")
        if not options["overwrite"]:
            queryset = queryset.filter(apellido="")

        changed = 0
        for partner in queryset.iterator():
            nombre, apellido = split_full_name(partner.nombre)
            if nombre == partner.nombre and apellido == partner.apellido:
                continue
            changed += 1
            self.stdout.write(
                f"{partner.pk}: '{partner.nombre_completo()}' -> nombres='{nombre}', apellidos='{apellido}'"
            )
            if options["apply"]:
                partner.nombre = nombre
                partner.apellido = apellido
                partner.save(update_fields=["nombre", "apellido"])

        action = "actualizados" if options["apply"] else "detectados"
        self.stdout.write(self.style.SUCCESS(f"{changed} registros {action}."))
