from django.contrib import admin

from .models import Aula, AulaHistorial, Curso, FichaInscripcion, PeriodoAcademico


@admin.register(PeriodoAcademico)
class PeriodoAcademicoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "empresa", "regimen", "fecha_inicio", "fecha_fin", "estado", "activo")
    list_filter = ("empresa", "estado", "activo")
    search_fields = ("nombre", "regimen")


@admin.register(Curso)
class CursoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "grado", "carrera", "universidad", "empresa", "activo")
    list_filter = ("empresa", "activo")
    search_fields = ("nombre", "grado", "carrera", "universidad")


@admin.register(Aula)
class AulaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "seccion", "periodo_academico", "jornada", "horario", "capacidad", "activo")
    list_filter = ("empresa", "periodo_academico", "jornada", "activo")
    search_fields = ("nombre", "seccion", "horario")


@admin.register(FichaInscripcion)
class FichaInscripcionAdmin(admin.ModelAdmin):
    list_display = ("numero", "fecha", "estudiante", "cliente", "periodo_academico", "aula", "saldo", "estado")
    list_filter = ("empresa", "periodo_academico", "aula", "estado", "forma_pago_convenio", "promo")
    search_fields = (
        "numero",
        "cliente__nombre",
        "cliente__identificacion",
        "estudiante__nombre",
        "estudiante__identificacion",
        "representante__nombre",
        "colegio",
        "carrera",
        "universidad",
    )
    date_hierarchy = "fecha"


@admin.register(AulaHistorial)
class AulaHistorialAdmin(admin.ModelAdmin):
    list_display = ("ficha_inscripcion", "aula_origen", "aula_destino", "fecha_cambio", "usuario")
    list_filter = ("aula_destino", "fecha_cambio")
    search_fields = ("ficha_inscripcion__numero", "ficha_inscripcion__estudiante__nombre", "motivo")
