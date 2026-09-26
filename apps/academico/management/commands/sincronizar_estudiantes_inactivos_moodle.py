from django.core.management.base import BaseCommand, CommandError

from apps.academico.moodle import MoodleClient, MoodleError
from apps.academico.moodle_users import suspend_inactive_students


class Command(BaseCommand):
    help = "Suspende en Moodle las cuentas de los estudiantes desactivados en el instituto."

    def add_arguments(self, parser):
        parser.add_argument(
            "--aplicar",
            action="store_true",
            help="Aplica la suspension. Sin esta opcion solo muestra una simulacion.",
        )

    def handle(self, *args, **options):
        apply = options["aplicar"]
        try:
            client = MoodleClient()
            accounts = suspend_inactive_students(client=client, apply=apply)
        except MoodleError as exc:
            raise CommandError(str(exc)) from None

        if not accounts:
            self.stdout.write(self.style.SUCCESS("No hay estudiantes inactivos pendientes de revisar."))
            return

        action = "SUSPENDER" if not apply else "SUSPENDIDO"
        for account in accounts:
            self.stdout.write(
                f"{action}: {account.persona.nombre_completo()} "
                f"(Moodle ID {account.usuario_id}, usuario {account.usuario})"
            )

        if apply:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Cuentas suspendidas en Moodle: {len(accounts)}."
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"Simulacion: {len(accounts)} cuenta(s) serian suspendidas. "
                    "Ejecuta nuevamente con --aplicar para confirmar."
                )
            )
