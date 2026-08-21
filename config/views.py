from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.academico.models import Asignatura, BancoPregunta, PlanificacionClase, Pregunta, Tema
from apps.cartera.models import Cuota, Pago
from apps.core.models import Empresa, Partner
from apps.matricula.models import Aula, FichaInscripcion, PeriodoAcademico


@login_required
def home(request):
    User = get_user_model()

    metrics = [
        {"label": "Empresas", "value": Empresa.objects.count(), "accent": "green"},
        {"label": "Estudiantes", "value": Partner.objects.filter(es_estudiante=True).count(), "accent": "blue"},
        {"label": "Fichas", "value": FichaInscripcion.objects.count(), "accent": "yellow"},
        {"label": "Cuotas pendientes", "value": Cuota.objects.exclude(estado="pagada").count(), "accent": "red"},
    ]

    modules = [
        {
            "title": "Administracion",
            "description": "Empresas, periodos, aulas, usuarios y roles.",
            "items": [
                ("Periodos", PeriodoAcademico.objects.count()),
                ("Aulas", Aula.objects.count()),
                ("Usuarios", User.objects.count()),
            ],
        },
        {
            "title": "Matriculas",
            "description": "Estudiantes, representantes, fichas y cambios de aula.",
            "items": [
                ("Estudiantes", Partner.objects.filter(es_estudiante=True).count()),
                ("Representantes", Partner.objects.filter(es_representante=True).count()),
                ("Fichas", FichaInscripcion.objects.count()),
            ],
        },
        {
            "title": "Academico",
            "description": "Temarios, temas, planificacion, preguntas y evaluaciones.",
            "items": [
                ("Materias", Asignatura.objects.count()),
                ("Temas", Tema.objects.count()),
                ("Planificaciones", PlanificacionClase.objects.count()),
            ],
        },
        {
            "title": "Cartera",
            "description": "Planes de pago, cuotas, comprobantes y semaforo.",
            "items": [
                ("Pagos", Pago.objects.count()),
                ("Bancos", BancoPregunta.objects.count()),
                ("Preguntas", Pregunta.objects.count()),
            ],
        },
    ]

    context = {
        "metrics": metrics,
        "modules": modules,
        "institution": Empresa.objects.first(),
        "active_period": PeriodoAcademico.objects.filter(estado="activo").first(),
    }
    return render(request, "dashboard/home.html", context)
