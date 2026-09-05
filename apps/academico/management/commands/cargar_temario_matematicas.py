from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.academico.models import Materia, MateriaSubtema, MateriaTema
from apps.academico.views import sync_materia_temas_to_materia_curso


TEMARIO = [
    (
        "Tema 1: Conjuntos y lógica matemática",
        "Lenguaje de conjuntos, relaciones y razonamiento lógico.",
        [
            "Concepto y representación de conjuntos",
            "Operaciones entre conjuntos",
            "Diagramas de Venn",
            "Proposiciones y conectores lógicos",
            "Tablas de verdad y razonamiento lógico",
        ],
    ),
    (
        "Tema 2: Números reales y operaciones",
        "Clasificación, propiedades y operaciones con números reales.",
        [
            "Números naturales, enteros, racionales e irracionales",
            "Operaciones combinadas y jerarquía operacional",
            "Potenciación y radicación",
            "Valor absoluto e intervalos",
            "Notación científica y aproximaciones",
        ],
    ),
    (
        "Tema 3: Razones, proporciones y porcentajes",
        "Aplicación de relaciones proporcionales a situaciones cotidianas.",
        [
            "Razones y proporciones",
            "Regla de tres simple y compuesta",
            "Porcentajes, descuentos e incrementos",
            "Reparto proporcional",
            "Interés simple y aplicaciones financieras",
        ],
    ),
    (
        "Tema 4: Expresiones algebraicas",
        "Representación simbólica y operaciones fundamentales del álgebra.",
        [
            "Lenguaje algebraico y términos semejantes",
            "Operaciones con polinomios",
            "Productos notables",
            "Factorización",
            "Fracciones algebraicas",
        ],
    ),
    (
        "Tema 5: Ecuaciones e inecuaciones",
        "Modelación y resolución de igualdades y desigualdades.",
        [
            "Ecuaciones lineales",
            "Sistemas de ecuaciones lineales",
            "Ecuaciones cuadráticas",
            "Inecuaciones e intervalos solución",
            "Problemas planteados con ecuaciones",
        ],
    ),
    (
        "Tema 6: Funciones y gráficas",
        "Análisis de relaciones funcionales y sus representaciones.",
        [
            "Concepto de función, dominio y rango",
            "Plano cartesiano y representación gráfica",
            "Función lineal y afín",
            "Función cuadrática",
            "Interpretación y transformación de gráficas",
        ],
    ),
    (
        "Tema 7: Geometría plana y del espacio",
        "Propiedades, medidas y relaciones de figuras geométricas.",
        [
            "Ángulos, rectas y polígonos",
            "Triángulos y congruencia",
            "Teorema de Pitágoras",
            "Perímetros y áreas",
            "Cuerpos geométricos, áreas y volúmenes",
        ],
    ),
    (
        "Tema 8: Trigonometría básica",
        "Relaciones trigonométricas y resolución de triángulos.",
        [
            "Razones trigonométricas",
            "Ángulos notables",
            "Resolución de triángulos rectángulos",
            "Ley de senos y ley de cosenos",
            "Aplicaciones de la trigonometría",
        ],
    ),
    (
        "Tema 9: Estadística descriptiva",
        "Organización, representación e interpretación de datos.",
        [
            "Población, muestra y variables",
            "Tablas de frecuencia",
            "Gráficos estadísticos",
            "Media, mediana y moda",
            "Rango, varianza y desviación estándar",
        ],
    ),
    (
        "Tema 10: Probabilidad y razonamiento matemático",
        "Análisis de situaciones aleatorias y estrategias de resolución.",
        [
            "Principios de conteo",
            "Espacio muestral y eventos",
            "Probabilidad simple",
            "Probabilidad compuesta",
            "Patrones, sucesiones y resolución de problemas",
        ],
    ),
]


class Command(BaseCommand):
    help = "Carga un temario completo e idempotente en las materias de Matemáticas."

    @transaction.atomic
    def handle(self, *args, **options):
        materias = list(Materia.objects.filter(nombre__icontains="matem"))
        if not materias:
            raise CommandError("No se encontró una materia cuyo nombre contenga 'matem'.")

        for materia in materias:
            temas_existentes = list(materia.temas_base.order_by("orden", "pk"))
            for order, (name, detail, subtopics) in enumerate(TEMARIO, start=1):
                tema = self._topic_for_position(materia, temas_existentes, order, name)
                tema.nombre = name
                tema.detalle = detail
                tema.orden = order
                tema.save()

                existentes = list(tema.subtemas_base.order_by("orden", "pk"))
                for suborder, subtopic_name in enumerate(subtopics, start=1):
                    subtema = existentes[suborder - 1] if suborder <= len(existentes) else MateriaSubtema(tema=tema)
                    subtema.nombre = subtopic_name
                    subtema.descripcion = None
                    subtema.orden = suborder
                    subtema.save()

            for materia_curso in materia.materia_cursos.all():
                sync_materia_temas_to_materia_curso(materia_curso)

            self.stdout.write(self.style.SUCCESS(
                f"{materia}: {len(TEMARIO)} temas y {sum(len(item[2]) for item in TEMARIO)} subtemas cargados."
            ))

    @staticmethod
    def _topic_for_position(materia, existing, order, name):
        exact = materia.temas_base.filter(nombre=name).first()
        if exact:
            return exact
        if order <= len(existing):
            return existing[order - 1]
        return MateriaTema(materia=materia)
