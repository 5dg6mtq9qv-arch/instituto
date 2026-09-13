from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils._os import safe_join
from django.utils.deconstruct import deconstructible


@deconstructible
class BolsaRecursosStorage(FileSystemStorage):
    @property
    def location(self):
        return str(settings.PRIVATE_MEDIA_ROOT)

    @property
    def base_url(self):
        return None

    def path(self, name):
        if name.startswith("academico/clase_recursos/"):
            return safe_join(settings.MEDIA_ROOT, name)
        return safe_join(self.location, name)
