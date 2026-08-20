from django.contrib import admin

from .models import AcademicPeriod, Classroom, Institution


@admin.register(Institution)
class InstitutionAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "tax_id", "is_active", "is_deleted")
    list_filter = ("is_active", "is_deleted")
    search_fields = ("code", "name", "legal_name", "tax_id")


@admin.register(AcademicPeriod)
class AcademicPeriodAdmin(admin.ModelAdmin):
    list_display = ("name", "institution", "start_date", "end_date", "status")
    list_filter = ("institution", "status")
    search_fields = ("name", "institution__name")


@admin.register(Classroom)
class ClassroomAdmin(admin.ModelAdmin):
    list_display = ("name", "section", "institution", "academic_period", "shift", "capacity", "is_active")
    list_filter = ("institution", "academic_period", "shift", "is_active")
    search_fields = ("name", "section", "institution__name")

# Register your models here.
