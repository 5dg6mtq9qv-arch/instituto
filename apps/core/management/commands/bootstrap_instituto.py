from datetime import date

from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.academico.models import Asignatura, BancoPregunta, Temario
from apps.cartera.models import FormaPago
from apps.core.group_seed import seed_default_groups
from apps.core.models import Empresa, TipoIdentificacion
from apps.matricula.models import Aula, Curso, PeriodoAcademico


class Command(BaseCommand):
    help = "Carga datos iniciales de Instituto con convencion Mantis."

    def add_arguments(self, parser):
        parser.add_argument("--admin-username", default="cristian")
        parser.add_argument("--admin-password", default=None)
        parser.add_argument("--admin-email", default="admin@instituto.local")

    @transaction.atomic
    def handle(self, *args, **options):
        empresa = self.crear_empresa()
        self.crear_catalogos()
        self.crear_grupos()
        self.crear_formas_pago(empresa)
        periodo = self.crear_periodo(empresa)
        curso = self.crear_curso(empresa)
        aula = self.crear_aula(empresa, periodo)
        self.crear_temarios(empresa, periodo)
        self.crear_usuario_admin(options)

        self.stdout.write(self.style.SUCCESS("Bootstrap Mantis-style completado."))
        self.stdout.write(f"Empresa: {empresa}")
        self.stdout.write(f"Periodo: {periodo}")
        self.stdout.write(f"Curso: {curso}")
        self.stdout.write(f"Aula: {aula}")

    def crear_empresa(self):
        empresa, _ = Empresa.objects.get_or_create(
            ruc="",
            defaults={
                "razon_social": "Centro de Aprendizaje Integral William James S.",
                "nombre_comercial": "Preuniversitario William James",
                "direccion": (
                    "Av. Carlos Emilio Grijalva entre Juan Genaro Jaramillo y "
                    "Av. Heleodoro Ayala, Ibarra, Ecuador"
                ),
                "telefono": "0989396225",
                "ciudad": "Ibarra",
                "activa": True,
            },
        )
        return empresa

    def crear_catalogos(self):
        datos = [
            ("Cedula", "05"),
            ("RUC", "04"),
            ("Pasaporte", "06"),
        ]
        for nombre, codigo in datos:
            TipoIdentificacion.objects.get_or_create(
                nombre=nombre,
                defaults={"codigo": codigo, "activo": True},
            )

    def crear_grupos(self):
        seed_default_groups()

    def crear_formas_pago(self, empresa):
        datos = [
            ("Efectivo", "efectivo", 1),
            ("Transferencia", "transferencia", 2),
            ("Cheque", "cheque", 3),
            ("Tarjeta de credito", "tarjeta_credito", 4),
            ("Deposito", "deposito", 5),
            ("Debito bancario", "debito_bancario", 6),
        ]
        for nombre, tipo, orden in datos:
            FormaPago.objects.get_or_create(
                empresa=empresa,
                tipo=tipo,
                defaults={
                    "nombre": nombre,
                    "orden": orden,
                    "activo": True,
                    "es_venta": True,
                    "es_pago": True,
                },
            )

    def crear_periodo(self, empresa):
        periodo, _ = PeriodoAcademico.objects.get_or_create(
            empresa=empresa,
            nombre="2026-2027",
            defaults={
                "regimen": "Sierra",
                "fecha_inicio": date(2026, 8, 19),
                "fecha_fin": date(2027, 7, 31),
                "estado": "activo",
                "activo": True,
            },
        )
        return periodo

    def crear_curso(self, empresa):
        curso, _ = Curso.objects.get_or_create(
            empresa=empresa,
            nombre="Preuniversitario",
            defaults={
                "grado": "Admision universitaria",
                "activo": True,
            },
        )
        return curso

    def crear_aula(self, empresa, periodo):
        aula, _ = Aula.objects.get_or_create(
            empresa=empresa,
            periodo_academico=periodo,
            nombre="Beta",
            seccion="A",
            defaults={
                "jornada": "Nocturna",
                "horario": "Por definir",
                "hora": "Por definir",
                "duracion": "Beta",
                "capacidad": 30,
                "activo": True,
            },
        )
        return aula

    def crear_temarios(self, empresa, periodo):
        for codigo, nombre in [("MAT", "Matematica"), ("LEN", "Lengua")]:
            asignatura, _ = Asignatura.objects.get_or_create(
                empresa=empresa,
                codigo=codigo,
                defaults={"nombre": nombre, "activo": True},
            )
            temario, _ = Temario.objects.get_or_create(
                empresa=empresa,
                periodo_academico=periodo,
                asignatura=asignatura,
                nombre=f"Temario beta {nombre}",
                defaults={"estado": "activo", "activo": True},
            )
            BancoPregunta.objects.get_or_create(
                empresa=empresa,
                asignatura=asignatura,
                tema=None,
                tipo="proceso",
                defaults={"meta_preguntas": 10, "activo": True},
            )
            BancoPregunta.objects.get_or_create(
                empresa=empresa,
                asignatura=asignatura,
                tema=None,
                tipo="final",
                defaults={"meta_preguntas": 10, "activo": True},
            )

    def crear_usuario_admin(self, options):
        username = options["admin_username"]
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": options["admin_email"],
                "is_staff": True,
                "is_superuser": True,
                "is_active": True,
            },
        )
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        if options["admin_password"]:
            user.set_password(options["admin_password"])
        elif created:
            user.set_unusable_password()
        user.save()
        user.groups.add(Group.objects.get(name="Administrador"))
