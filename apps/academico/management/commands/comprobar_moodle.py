from django.core.management.base import BaseCommand, CommandError

from apps.academico.moodle import MoodleClient, MoodleError


class Command(BaseCommand):
    help = "Comprueba Moodle y lista categorías sin crear ni modificar cursos."

    def handle(self, *args, **options):
        client = MoodleClient()
        try:
            info = client.site_info()
            missing = client.missing_functions(info)
            if missing:
                raise CommandError("Faltan funciones en el servicio: " + ", ".join(sorted(missing)))
            categories = client.categories()
        except MoodleError as exc:
            raise CommandError(str(exc)) from None
        self.stdout.write(self.style.SUCCESS(f"Conexión correcta. Moodle {info.get('release', '')}"))
        self.stdout.write("Funciones necesarias disponibles. Categorías:")
        for category in categories:
            self.stdout.write(f"  {category['id']}: {category['name']}")
        if not categories:
            self.stdout.write("  No hay categorías accesibles para este usuario.")
