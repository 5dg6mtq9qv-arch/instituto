from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count, Max

from apps.academico.models import MateriaCurso, PlanificacionDocente, PlanificacionTema, ProfesorMateriaCurso, Subtema, Tema


TOPICS_BY_SUBJECT = {
    "matematica": [
        (
            "Aritmetica y numeros reales",
            "Operaciones, propiedades y resolucion de ejercicios con numeros reales.",
            [
                "Operaciones combinadas",
                "Fracciones, decimales y porcentajes",
                "Potenciacion y radicacion",
            ],
        ),
        (
            "Algebra y ecuaciones",
            "Lenguaje algebraico, productos notables, factorizacion y ecuaciones.",
            [
                "Expresiones algebraicas",
                "Ecuaciones lineales y cuadraticas",
                "Sistemas de ecuaciones",
            ],
        ),
        (
            "Funciones y graficas",
            "Analisis de funciones, dominio, rango y representaciones graficas.",
            [
                "Plano cartesiano",
                "Funciones lineales y cuadraticas",
                "Interpretacion de graficas",
            ],
        ),
        (
            "Geometria y trigonometria",
            "Figuras, medidas, relaciones metricas y razones trigonometricas.",
            [
                "Perimetros, areas y volumenes",
                "Teorema de Pitagoras",
                "Razones trigonometricas",
            ],
        ),
        (
            "Estadistica y probabilidad",
            "Organizacion de datos, medidas estadisticas y calculo de probabilidades.",
            [
                "Tablas y graficos estadisticos",
                "Media, mediana y moda",
                "Probabilidad simple",
            ],
        ),
        (
            "Razonamiento matematico",
            "Estrategias para resolver problemas logicos y cuantitativos.",
            [
                "Patrones y sucesiones",
                "Problemas de conteo",
                "Planteamiento de problemas",
            ],
        ),
    ],
    "lenguaje": [
        (
            "Lectura comprensiva",
            "Comprension literal, inferencial y critica de textos.",
            [
                "Ideas principales y secundarias",
                "Inferencias y conclusiones",
                "Tipos de texto",
            ],
        ),
        (
            "Gramatica y ortografia",
            "Uso correcto de categorias gramaticales, signos y normas ortograficas.",
            [
                "Categorias gramaticales",
                "Acentuacion y puntuacion",
                "Concordancia y cohesion",
            ],
        ),
        (
            "Redaccion academica",
            "Produccion de textos claros, coherentes y adecuados al proposito.",
            [
                "Parrafos y conectores",
                "Ensayo corto",
                "Revision y correccion",
            ],
        ),
        (
            "Literatura ecuatoriana y latinoamericana",
            "Lectura de obras, autores y movimientos literarios relevantes.",
            [
                "Generos literarios",
                "Figuras literarias",
                "Contexto historico de obras",
            ],
        ),
        (
            "Comunicacion oral",
            "Expresion oral, argumentacion y escucha activa.",
            [
                "Exposicion oral",
                "Debate y argumentacion",
                "Recursos verbales y no verbales",
            ],
        ),
        (
            "Razonamiento verbal",
            "Analisis de relaciones semanticas y logicas del lenguaje.",
            [
                "Sinonimos y antonimos",
                "Analogias verbales",
                "Comprension de enunciados",
            ],
        ),
    ],
    "ingles": [
        (
            "Comunicacion basica en ingles",
            "Uso de expresiones cotidianas para presentarse y comunicarse.",
            [
                "Greetings and introductions",
                "Personal information",
                "Classroom language",
            ],
        ),
        (
            "Estructuras gramaticales",
            "Reconocimiento y uso de tiempos verbales y estructuras frecuentes.",
            [
                "Verb to be and present simple",
                "Past simple",
                "Future forms",
            ],
        ),
        (
            "Comprension lectora",
            "Lectura de textos breves y extraccion de informacion clave.",
            [
                "Main ideas",
                "Specific information",
                "Context clues",
            ],
        ),
        (
            "Escucha y pronunciacion",
            "Practica de sonidos, entonacion y comprension auditiva.",
            [
                "Basic phonetics",
                "Listening for details",
                "Pronunciation drills",
            ],
        ),
        (
            "Escritura guiada",
            "Produccion de oraciones y textos breves en ingles.",
            [
                "Sentence structure",
                "Short paragraphs",
                "Email and messages",
            ],
        ),
        (
            "Vocabulario en contexto",
            "Ampliacion de vocabulario por situaciones comunicativas.",
            [
                "Daily routines",
                "Places and directions",
                "Health, food and travel",
            ],
        ),
    ],
    "historia": [
        (
            "Origenes de la humanidad",
            "Procesos de hominizacion, primeras sociedades y vida sedentaria.",
            [
                "Prehistoria",
                "Revolucion agricola",
                "Primeras aldeas",
            ],
        ),
        (
            "Civilizaciones antiguas",
            "Organizacion social, politica y cultural de las primeras civilizaciones.",
            [
                "Mesopotamia y Egipto",
                "Grecia y Roma",
                "Legados culturales",
            ],
        ),
        (
            "Historia del Ecuador",
            "Etapas historicas del territorio ecuatoriano y sus transformaciones.",
            [
                "Pueblos originarios",
                "Epoca colonial",
                "Construccion republicana",
            ],
        ),
        (
            "Independencia y republica",
            "Procesos independentistas y formacion de estados nacionales.",
            [
                "Causas de independencia",
                "Personajes y movimientos",
                "Organizacion republicana",
            ],
        ),
        (
            "Siglo XX y mundo actual",
            "Conflictos, cambios sociales y transformaciones politicas contemporaneas.",
            [
                "Guerras mundiales",
                "Guerra fria",
                "Globalizacion",
            ],
        ),
        (
            "Ciudadania historica",
            "Analisis de memoria, identidad y participacion social.",
            [
                "Identidad cultural",
                "Memoria social",
                "Fuentes historicas",
            ],
        ),
    ],
    "fisica": [
        (
            "Magnitudes y vectores",
            "Medicion, unidades, conversiones y representacion vectorial.",
            [
                "Sistema internacional",
                "Conversion de unidades",
                "Suma de vectores",
            ],
        ),
        (
            "Cinematica",
            "Descripcion del movimiento en una y dos dimensiones.",
            [
                "Movimiento rectilineo uniforme",
                "Movimiento acelerado",
                "Graficas de movimiento",
            ],
        ),
        (
            "Dinamica",
            "Estudio de fuerzas, leyes de Newton y equilibrio.",
            [
                "Leyes de Newton",
                "Fuerza de rozamiento",
                "Equilibrio de cuerpos",
            ],
        ),
        (
            "Energia y trabajo",
            "Relacion entre trabajo, energia, potencia y conservacion.",
            [
                "Trabajo mecanico",
                "Energia cinetica y potencial",
                "Conservacion de energia",
            ],
        ),
        (
            "Electricidad y magnetismo",
            "Carga electrica, circuitos simples y fenomenos magneticos.",
            [
                "Ley de Ohm",
                "Circuitos electricos",
                "Campo magnetico",
            ],
        ),
        (
            "Ondas y optica",
            "Propagacion de ondas, sonido, luz y fenomenos opticos.",
            [
                "Caracteristicas de ondas",
                "Reflexion y refraccion",
                "Lentes y espejos",
            ],
        ),
    ],
    "quimica": [
        (
            "Materia y medicion",
            "Propiedades de la materia, cambios fisicos y quimicos, y mediciones.",
            [
                "Propiedades intensivas y extensivas",
                "Estados de la materia",
                "Mezclas y sustancias puras",
            ],
        ),
        (
            "Estructura atomica",
            "Modelos atomicos, particulas subatomicas y configuracion electronica.",
            [
                "Particulas subatomicas",
                "Numero atomico y masico",
                "Configuracion electronica",
            ],
        ),
        (
            "Tabla periodica y enlace",
            "Organizacion periodica, propiedades y tipos de enlace quimico.",
            [
                "Grupos y periodos",
                "Enlace ionico y covalente",
                "Propiedades periodicas",
            ],
        ),
        (
            "Reacciones quimicas",
            "Representacion, clasificacion y balanceo de ecuaciones quimicas.",
            [
                "Tipos de reacciones",
                "Balanceo por tanteo",
                "Ley de conservacion de masa",
            ],
        ),
        (
            "Estequiometria",
            "Calculos quimicos con moles, masas y relaciones de reaccion.",
            [
                "Mol y masa molar",
                "Relaciones molares",
                "Reactivo limitante",
            ],
        ),
        (
            "Quimica organica basica",
            "Introduccion a compuestos de carbono y funciones organicas.",
            [
                "Hidrocarburos",
                "Grupos funcionales",
                "Nomenclatura basica",
            ],
        ),
    ],
    "biologia": [
        (
            "Celula y biomoleculas",
            "Estructura celular y moleculas esenciales para la vida.",
            [
                "Celula procariota y eucariota",
                "Organulos celulares",
                "Carbohidratos, lipidos y proteinas",
            ],
        ),
        (
            "Genetica",
            "Herencia biologica, ADN y variabilidad genetica.",
            [
                "ADN y genes",
                "Leyes de Mendel",
                "Mutaciones",
            ],
        ),
        (
            "Evolucion",
            "Procesos evolutivos, seleccion natural y adaptacion.",
            [
                "Evidencias de evolucion",
                "Seleccion natural",
                "Adaptaciones",
            ],
        ),
        (
            "Anatomia y fisiologia",
            "Sistemas del cuerpo humano y funciones vitales.",
            [
                "Sistema digestivo",
                "Sistema circulatorio",
                "Sistema nervioso",
            ],
        ),
        (
            "Ecologia",
            "Relaciones entre seres vivos y ambiente.",
            [
                "Ecosistemas",
                "Cadenas troficas",
                "Ciclos biogeoquimicos",
            ],
        ),
        (
            "Salud y biotecnologia",
            "Aplicaciones biologicas en salud, ambiente y tecnologia.",
            [
                "Prevencion de enfermedades",
                "Biotecnologia basica",
                "Bioetica",
            ],
        ),
    ],
    "educacion fisica": [
        (
            "Condicion fisica",
            "Desarrollo de capacidades fisicas y seguimiento del rendimiento.",
            [
                "Resistencia",
                "Fuerza y flexibilidad",
                "Velocidad y coordinacion",
            ],
        ),
        (
            "Deportes colectivos",
            "Reglas, fundamentos tecnicos y trabajo en equipo.",
            [
                "Futbol y baloncesto",
                "Voleibol",
                "Estrategia de equipo",
            ],
        ),
        (
            "Atletismo",
            "Practica de carreras, saltos y lanzamientos.",
            [
                "Carreras de velocidad",
                "Saltos",
                "Lanzamientos",
            ],
        ),
        (
            "Expresion corporal",
            "Movimiento, ritmo y comunicacion corporal.",
            [
                "Ritmo y coordinacion",
                "Coreografias",
                "Lenguaje corporal",
            ],
        ),
        (
            "Salud y nutricion",
            "Habitos saludables asociados a la actividad fisica.",
            [
                "Calentamiento y vuelta a la calma",
                "Hidratacion",
                "Prevencion de lesiones",
            ],
        ),
        (
            "Juego limpio",
            "Valores, respeto de reglas y convivencia en el deporte.",
            [
                "Respeto y cooperacion",
                "Reglamento deportivo",
                "Resolucion de conflictos",
            ],
        ),
    ],
    "educacion para la ciudadania": [
        (
            "Derechos humanos",
            "Principios, garantias y responsabilidades vinculadas a los derechos.",
            [
                "Dignidad humana",
                "Derechos y deberes",
                "Proteccion de derechos",
            ],
        ),
        (
            "Estado y democracia",
            "Organizacion del Estado, poderes y principios democraticos.",
            [
                "Funciones del Estado",
                "Democracia representativa",
                "Control ciudadano",
            ],
        ),
        (
            "Participacion ciudadana",
            "Mecanismos de participacion y toma de decisiones colectivas.",
            [
                "Participacion comunitaria",
                "Voto responsable",
                "Organizaciones sociales",
            ],
        ),
        (
            "Constitucion del Ecuador",
            "Estructura, derechos y garantias constitucionales.",
            [
                "Principios constitucionales",
                "Garantias jurisdiccionales",
                "Ciudadania y nacionalidad",
            ],
        ),
        (
            "Convivencia y cultura de paz",
            "Practicas para una convivencia democratica e inclusiva.",
            [
                "Normas de convivencia",
                "Mediacion de conflictos",
                "Inclusividad",
            ],
        ),
        (
            "Problemas sociales contemporaneos",
            "Analisis ciudadano de desafios sociales actuales.",
            [
                "Desigualdad",
                "Movilidad humana",
                "Ambiente y sociedad",
            ],
        ),
    ],
    "emprendimiento y gestion": [
        (
            "Perfil emprendedor",
            "Actitudes, habilidades y competencias para emprender.",
            [
                "Creatividad e innovacion",
                "Liderazgo",
                "Toma de decisiones",
            ],
        ),
        (
            "Ideas de negocio",
            "Identificacion de problemas, oportunidades y propuestas de valor.",
            [
                "Necesidades del entorno",
                "Validacion de ideas",
                "Propuesta de valor",
            ],
        ),
        (
            "Modelo Canvas",
            "Estructura de modelo de negocio usando bloques principales.",
            [
                "Segmentos de clientes",
                "Canales y relacion",
                "Ingresos y recursos clave",
            ],
        ),
        (
            "Costos y presupuesto",
            "Calculo basico de costos, precios y presupuesto inicial.",
            [
                "Costos fijos y variables",
                "Punto de equilibrio",
                "Flujo de caja basico",
            ],
        ),
        (
            "Marketing basico",
            "Estrategias para comunicar y vender una propuesta.",
            [
                "Cliente objetivo",
                "Producto, precio y promocion",
                "Canales digitales",
            ],
        ),
        (
            "Proyecto final",
            "Integracion de aprendizajes en un proyecto emprendedor.",
            [
                "Plan de accion",
                "Presentacion del proyecto",
                "Evaluacion de resultados",
            ],
        ),
    ],
}

DEFAULT_TOPICS = [
    (
        "Fundamentos de la materia",
        "Conceptos base, vocabulario tecnico y ejercicios iniciales.",
        ["Conceptos principales", "Ejercicios guiados", "Retroalimentacion"],
    ),
    (
        "Aplicaciones practicas",
        "Resolucion de actividades contextualizadas y trabajo colaborativo.",
        ["Casos practicos", "Trabajo en equipo", "Problemas aplicados"],
    ),
    (
        "Evaluacion y refuerzo",
        "Practica individual, revision de errores y preparacion de evaluaciones.",
        ["Practica individual", "Correccion de errores", "Preparacion de prueba"],
    ),
]

MIN_SUBTOPICS_PER_TOPIC = 5
SUPPLEMENTAL_SUBTOPICS = [
    "Diagnostico de saberes previos",
    "Conceptos clave",
    "Ejercicios guiados",
    "Practica aplicada",
    "Resolucion de casos",
    "Trabajo colaborativo",
    "Refuerzo y retroalimentacion",
    "Evaluacion formativa",
]

SUBJECT_ALIASES = {
    "lengua y literatura": "lenguaje",
    "lengua": "lenguaje",
    "matematicas": "matematica",
}


def subject_key(name):
    normalized = " ".join(name.lower().strip().split())
    return SUBJECT_ALIASES.get(normalized, normalized)


def get_topic_data(materia):
    return TOPICS_BY_SUBJECT.get(subject_key(materia.nombre), DEFAULT_TOPICS)


class Command(BaseCommand):
    help = "Carga temas y subtemas demo por materia-grupo para pruebas."

    def add_arguments(self, parser):
        parser.add_argument(
            "--solo-vacios",
            action="store_true",
            help="Carga datos solo en materia-grupo sin temas registrados.",
        )
        parser.add_argument(
            "--min-subtemas",
            type=int,
            default=MIN_SUBTOPICS_PER_TOPIC,
            help="Cantidad minima de subtemas que debe tener cada tema procesado.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        only_empty = options["solo_vacios"]
        min_subtemas = max(options["min_subtemas"], 0)
        total_plans = 0
        created_plans = 0
        created_topic_plans = 0
        created_topics = 0
        created_subtopics = 0
        skipped = 0

        materia_cursos = (
            MateriaCurso.objects.select_related("materia", "grupo")
            .annotate(topic_count=Count("planificaciones__temas_planificacion", distinct=True))
            .order_by("grupo__nombre", "materia__nombre")
        )

        for materia_curso in materia_cursos:
            if only_empty and materia_curso.topic_count:
                skipped += 1
                continue

            planificacion = (
                PlanificacionDocente.objects.filter(materia_curso=materia_curso)
                .order_by("id")
                .first()
            )
            if planificacion is None:
                planificacion = PlanificacionDocente.objects.create(
                    materia_curso=materia_curso,
                    nombre=f"{materia_curso.grupo} - {materia_curso.materia}",
                )
                created_plans += 1
            total_plans += 1

            next_order = (planificacion.temas_planificacion.aggregate(Max("orden"))["orden__max"] or 0) + 1
            for nombre, detalle, subtemas in get_topic_data(materia_curso.materia):
                tema = (
                    Tema.objects.filter(planificacion=planificacion, nombre=nombre)
                    .order_by("id")
                    .first()
                )
                if tema is None:
                    tema = Tema.objects.create(
                        planificacion=planificacion,
                        nombre=nombre,
                        detalle=detalle,
                        orden=next_order,
                    )
                    created_topics += 1
                    next_order += 1
                elif not tema.detalle:
                    tema.detalle = detalle
                    tema.save(update_fields=["detalle"])

                next_subtopic_order = (
                    tema.subtemas_planificacion.aggregate(Max("orden"))["orden__max"] or 0
                ) + 1
                for subtema_nombre in subtemas:
                    subtema = (
                        Subtema.objects.filter(tema=tema, nombre=subtema_nombre)
                        .order_by("id")
                        .first()
                    )
                    if subtema is None:
                        Subtema.objects.create(
                            tema=tema,
                            nombre=subtema_nombre,
                            orden=next_subtopic_order,
                        )
                        created_subtopics += 1
                        next_subtopic_order += 1

            created_subtopics += self.ensure_min_subtemas(planificacion, min_subtemas)

            for profesor_materia_curso in ProfesorMateriaCurso.objects.filter(
                materia_curso=materia_curso,
            ).select_related("partner"):
                for tema in planificacion.temas_planificacion.all():
                    _, created = PlanificacionTema.objects.get_or_create(
                        profesor_materia_curso=profesor_materia_curso,
                        tema=tema,
                        defaults={
                            "nombre": f"{materia_curso.grupo} - {materia_curso.materia} - {tema.nombre}",
                        },
                    )
                    if created:
                        created_topic_plans += 1

        self.stdout.write(self.style.SUCCESS("Seed de temas demo completado."))
        self.stdout.write(f"Materia-grupo procesadas: {total_plans}")
        self.stdout.write(f"Materia-grupo omitidas: {skipped}")
        self.stdout.write(f"Planificaciones creadas: {created_plans}")
        self.stdout.write(f"Planificaciones por tema creadas: {created_topic_plans}")
        self.stdout.write(f"Temas creados: {created_topics}")
        self.stdout.write(f"Subtemas creados: {created_subtopics}")

    def ensure_min_subtemas(self, planificacion, min_subtemas):
        if not min_subtemas:
            return 0
        created = 0
        for tema in planificacion.temas_planificacion.all():
            current_count = tema.subtemas_planificacion.count()
            if current_count >= min_subtemas:
                continue
            existing_names = {
                nombre.lower()
                for nombre in tema.subtemas_planificacion.values_list("nombre", flat=True)
            }
            next_order = (tema.subtemas_planificacion.aggregate(Max("orden"))["orden__max"] or 0) + 1
            for subtema_nombre in SUPPLEMENTAL_SUBTOPICS:
                if current_count >= min_subtemas:
                    break
                if subtema_nombre.lower() in existing_names:
                    continue
                Subtema.objects.create(
                    tema=tema,
                    nombre=subtema_nombre,
                    orden=next_order,
                )
                existing_names.add(subtema_nombre.lower())
                current_count += 1
                created += 1
                next_order += 1
        return created
