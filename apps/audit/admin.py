from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "institution", "actor", "action", "model_name", "object_pk")
    list_filter = ("institution", "action", "model_name", "created_at")
    search_fields = ("actor__username", "model_name", "object_pk", "object_repr")
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "created_at"

# Register your models here.
