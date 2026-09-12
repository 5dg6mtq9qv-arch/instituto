from django.contrib import admin

from .models import LogAccion, PagoAuditoria


def is_system_administrator(user):
    return bool(
        user
        and user.is_authenticated
        and (user.is_superuser or user.groups.filter(name="Administrador").exists())
    )


@admin.register(LogAccion)
class LogAccionAdmin(admin.ModelAdmin):
    list_display = ("created", "empresa", "usuario", "accion", "modelo", "object_id")
    list_filter = ("empresa", "accion", "modelo", "created")
    search_fields = ("usuario__username", "modelo", "object_id", "object_repr")
    readonly_fields = ("created",)
    date_hierarchy = "created"


@admin.register(PagoAuditoria)
class PagoAuditoriaAdmin(admin.ModelAdmin):
    list_display = (
        "created",
        "accion",
        "pago_id",
        "ficha_inscripcion_id",
        "cuota_id",
        "usuario_accion_id",
        "usuario_accion_username",
    )
    list_filter = ("accion", "created")
    search_fields = (
        "=pago_id",
        "=ficha_inscripcion_id",
        "=cuota_id",
        "=usuario_accion_id",
        "usuario_accion_username",
    )
    readonly_fields = tuple(field.name for field in PagoAuditoria._meta.fields)
    date_hierarchy = "created"

    def has_module_permission(self, request):
        return is_system_administrator(request.user)

    def has_view_permission(self, request, obj=None):
        return is_system_administrator(request.user)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
