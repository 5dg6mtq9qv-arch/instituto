from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.AutoField"
    name = "apps.core"
    verbose_name = "Core"

    def ready(self):
        from . import group_seed  # noqa: F401
        from . import signals  # noqa: F401
