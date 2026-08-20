from django.contrib import admin

from .models import LogAccion


@admin.register(LogAccion)
class LogAccionAdmin(admin.ModelAdmin):
    list_display = ("created", "empresa", "usuario", "accion", "modelo", "object_id")
    list_filter = ("empresa", "accion", "modelo", "created")
    search_fields = ("usuario__username", "modelo", "object_id", "object_repr")
    readonly_fields = ("created",)
    date_hierarchy = "created"
