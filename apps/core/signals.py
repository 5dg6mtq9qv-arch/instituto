from django.db.models.signals import pre_save
from django.dispatch import receiver

from .current_user import get_current_request


@receiver(pre_save)
def add_usuario_updated(sender, instance, **kwargs):
    try:
        field = sender._meta.get_field("usuario_updated")
    except Exception:
        return

    request = get_current_request()
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return

    if field.remote_field and field.remote_field.model == user.__class__:
        instance.usuario_updated = user
