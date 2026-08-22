from django.contrib import admin

from .models import (
    Asignatura,
    Asistencia,
    BancoPregunta,
    DocenteAsignatura,
    Evaluacion,
    EvaluacionResultado,
    HorarioClase,
    PlanificacionClase,
    Pregunta,
    RecursoClase,
    Subtema,
    Tema,
    Temario,
)


class SubtemaInline(admin.TabularInline):
    model = Subtema
    extra = 0


class RecursoClaseInline(admin.TabularInline):
    model = RecursoClase
    extra = 0


class EvaluacionResultadoInline(admin.TabularInline):
    model = EvaluacionResultado
    extra = 0


@admin.register(Asignatura)
class AsignaturaAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre", "empresa", "activo")
    list_filter = ("empresa", "activo")
    search_fields = ("codigo", "nombre")


@admin.register(Temario)
class TemarioAdmin(admin.ModelAdmin):
    list_display = ("nombre", "asignatura", "periodo_academico", "estado", "activo")
    list_filter = ("empresa", "asignatura", "estado", "activo")
    search_fields = ("nombre", "asignatura__nombre")


@admin.register(Tema)
class TemaAdmin(admin.ModelAdmin):
    list_display = (
        "nombre",
        "temario",
        "orden",
        "dificultad",
        "numero_clases",
        "meta_preguntas_proceso",
        "meta_preguntas_final",
        "activo",
    )
    list_filter = ("temario__asignatura", "dificultad", "activo")
    search_fields = ("nombre", "temario__nombre", "temario__asignatura__nombre")
    inlines = [SubtemaInline]


@admin.register(Subtema)
class SubtemaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "tema", "orden", "activo")
    list_filter = ("tema__temario__asignatura", "activo")
    search_fields = ("nombre", "tema__nombre")


@admin.register(DocenteAsignatura)
class DocenteAsignaturaAdmin(admin.ModelAdmin):
    list_display = ("docente", "asignatura", "periodo_academico", "aula", "activo")
    list_filter = ("empresa", "periodo_academico", "asignatura", "activo")
    search_fields = ("docente__nombre", "asignatura__nombre")


@admin.register(HorarioClase)
class HorarioClaseAdmin(admin.ModelAdmin):
    list_display = ("fecha", "hora_inicio", "hora_fin", "aula", "asignatura", "docente", "estado", "activo")
    list_filter = ("empresa", "periodo_academico", "aula", "asignatura", "estado", "activo")
    search_fields = ("docente__nombre", "asignatura__nombre", "aula__nombre", "tema_previsto", "observacion")
    date_hierarchy = "fecha"


@admin.register(PlanificacionClase)
class PlanificacionClaseAdmin(admin.ModelAdmin):
    list_display = ("asignatura", "tema", "docente", "aula", "fecha_planificada", "estado", "activo")
    list_filter = ("empresa", "asignatura", "estado", "fecha_planificada", "activo")
    search_fields = ("docente__nombre", "asignatura__nombre", "tema__nombre", "objetivo")
    date_hierarchy = "fecha_planificada"
    inlines = [RecursoClaseInline]


@admin.register(RecursoClase)
class RecursoClaseAdmin(admin.ModelAdmin):
    list_display = ("titulo", "planificacion_clase", "tipo", "listo", "creado_por")
    list_filter = ("tipo", "listo")
    search_fields = ("titulo", "planificacion_clase__tema__nombre")


@admin.register(BancoPregunta)
class BancoPreguntaAdmin(admin.ModelAdmin):
    list_display = ("asignatura", "tema", "subtema", "tipo", "meta_preguntas", "revisado_coordinacion", "activo")
    list_filter = ("empresa", "asignatura", "tipo", "revisado_coordinacion", "activo")
    search_fields = ("asignatura__nombre", "tema__nombre", "subtema__nombre")


@admin.register(Pregunta)
class PreguntaAdmin(admin.ModelAdmin):
    list_display = ("banco_pregunta", "creado_por", "dificultad", "estado", "created", "activo")
    list_filter = ("banco_pregunta__asignatura", "banco_pregunta__tipo", "dificultad", "estado", "activo")
    search_fields = ("enunciado", "creado_por__nombre")


@admin.register(Asistencia)
class AsistenciaAdmin(admin.ModelAdmin):
    list_display = ("planificacion_clase", "estudiante", "estado", "registrado_por")
    list_filter = ("estado", "planificacion_clase__fecha_planificada")
    search_fields = ("estudiante__nombre", "planificacion_clase__tema__nombre")


@admin.register(Evaluacion)
class EvaluacionAdmin(admin.ModelAdmin):
    list_display = ("titulo", "asignatura", "tema", "tipo", "fecha", "puntaje_maximo")
    list_filter = ("empresa", "asignatura", "tipo", "fecha")
    search_fields = ("titulo", "asignatura__nombre", "tema__nombre")
    date_hierarchy = "fecha"
    inlines = [EvaluacionResultadoInline]


@admin.register(EvaluacionResultado)
class EvaluacionResultadoAdmin(admin.ModelAdmin):
    list_display = ("evaluacion", "estudiante", "nota")
    list_filter = ("evaluacion__asignatura",)
    search_fields = ("estudiante__nombre", "evaluacion__titulo")
