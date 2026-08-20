from django.contrib import admin

from .models import (
    ClassroomHistory,
    Enrollment,
    Representative,
    Student,
    StudentRepresentative,
)


class StudentRepresentativeInline(admin.TabularInline):
    model = StudentRepresentative
    extra = 0


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("document_number", "last_names", "first_names", "institution", "status")
    list_filter = ("institution", "status", "is_deleted")
    search_fields = ("document_number", "first_names", "last_names", "email", "phone")
    inlines = [StudentRepresentativeInline]


@admin.register(Representative)
class RepresentativeAdmin(admin.ModelAdmin):
    list_display = ("document_number", "last_names", "first_names", "institution", "phone", "email")
    list_filter = ("institution", "is_deleted")
    search_fields = ("document_number", "first_names", "last_names", "phone", "email")


@admin.register(StudentRepresentative)
class StudentRepresentativeAdmin(admin.ModelAdmin):
    list_display = ("student", "representative", "relationship", "is_primary", "emergency_contact")
    list_filter = ("relationship", "is_primary", "emergency_contact")
    search_fields = ("student__first_names", "student__last_names", "representative__first_names", "representative__last_names")


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ("student", "academic_period", "classroom", "enrollment_date", "status")
    list_filter = ("institution", "academic_period", "classroom", "status", "is_deleted")
    search_fields = ("student__first_names", "student__last_names", "student__document_number", "code")
    date_hierarchy = "enrollment_date"


@admin.register(ClassroomHistory)
class ClassroomHistoryAdmin(admin.ModelAdmin):
    list_display = ("enrollment", "from_classroom", "to_classroom", "changed_by", "changed_at")
    list_filter = ("to_classroom", "changed_at")
    search_fields = ("enrollment__student__first_names", "enrollment__student__last_names", "reason")

# Register your models here.
