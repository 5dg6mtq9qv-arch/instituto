from django.core.management.base import BaseCommand

from apps.academico.attendance_closure import close_overdue_attendances


class Command(BaseCommand):
    help = "Cierra asistencias de clases anteriores al día actual sin alterar las marcas de los alumnos."

    def handle(self, *args, **options):
        count = close_overdue_attendances()
        self.stdout.write(self.style.SUCCESS(f"Asistencias cerradas automáticamente: {count}"))
