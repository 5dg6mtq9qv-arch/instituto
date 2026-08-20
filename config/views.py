from django.contrib.auth import get_user_model
from django.shortcuts import render

from apps.academic.models import LessonPlan, Question, QuestionBank, Subject, Topic
from apps.finance.models import Installment, Payment
from apps.institutions.models import AcademicPeriod, Classroom, Institution
from apps.people.models import Enrollment, Representative, Student


def home(request):
    User = get_user_model()

    metrics = [
        {"label": "Instituciones", "value": Institution.objects.count(), "accent": "green"},
        {"label": "Estudiantes", "value": Student.objects.count(), "accent": "blue"},
        {"label": "Matriculas", "value": Enrollment.objects.count(), "accent": "yellow"},
        {"label": "Cuotas pendientes", "value": Installment.objects.exclude(status="paid").count(), "accent": "red"},
    ]

    modules = [
        {
            "title": "Administracion",
            "description": "Instituciones, periodos, aulas, usuarios y roles.",
            "items": [
                ("Periodos", AcademicPeriod.objects.count()),
                ("Aulas", Classroom.objects.count()),
                ("Usuarios", User.objects.count()),
            ],
        },
        {
            "title": "Matriculas",
            "description": "Estudiantes, representantes, fichas y cambios de aula.",
            "items": [
                ("Estudiantes", Student.objects.count()),
                ("Representantes", Representative.objects.count()),
                ("Matriculas", Enrollment.objects.count()),
            ],
        },
        {
            "title": "Academico",
            "description": "Temarios, temas, planificacion, preguntas y evaluaciones.",
            "items": [
                ("Materias", Subject.objects.count()),
                ("Temas", Topic.objects.count()),
                ("Planificaciones", LessonPlan.objects.count()),
            ],
        },
        {
            "title": "Cartera",
            "description": "Planes de pago, cuotas, comprobantes y semaforo.",
            "items": [
                ("Pagos", Payment.objects.count()),
                ("Bancos", QuestionBank.objects.count()),
                ("Preguntas", Question.objects.count()),
            ],
        },
    ]

    context = {
        "metrics": metrics,
        "modules": modules,
        "institution": Institution.objects.first(),
        "active_period": AcademicPeriod.objects.filter(status="active").first(),
    }
    return render(request, "dashboard/home.html", context)
