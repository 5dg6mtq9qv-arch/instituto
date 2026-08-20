from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.academic.models import Subject, Syllabus, Topic
from apps.accounts.models import User
from apps.institutions.models import AcademicPeriod, Classroom, Institution


class Command(BaseCommand):
    help = "Creates the initial institution, roles, period, classroom, and beta academic data."

    def add_arguments(self, parser):
        parser.add_argument("--admin-username", default="cristian")
        parser.add_argument("--institution-code", default="instituto")
        parser.add_argument("--institution-name", default="Instituto")
        parser.add_argument("--period-name", default="2026-2027")
        parser.add_argument("--start-date", default="2026-08-19")
        parser.add_argument("--end-date", default="2027-07-31")
        parser.add_argument("--classroom-name", default="Beta")
        parser.add_argument("--classroom-section", default="A")

    @transaction.atomic
    def handle(self, *args, **options):
        institution = self.create_institution(options)
        self.create_role_groups()
        period = self.create_period(institution, options)
        classroom = self.create_classroom(institution, period, options)
        subjects = self.create_beta_subjects(institution, period)
        self.assign_admin_user(institution, options["admin_username"])

        self.stdout.write(self.style.SUCCESS("Bootstrap completado."))
        self.stdout.write(f"Institucion: {institution.name} ({institution.code})")
        self.stdout.write(f"Periodo: {period.name}")
        self.stdout.write(f"Aula: {classroom.name} {classroom.section}".strip())
        self.stdout.write(f"Materias: {', '.join(subject.name for subject in subjects)}")

    def create_institution(self, options):
        institution, _ = Institution.objects.get_or_create(
            code=options["institution_code"],
            defaults={
                "name": options["institution_name"],
                "legal_name": options["institution_name"],
                "is_active": True,
            },
        )
        return institution

    def create_role_groups(self):
        group_names = {
            User.Role.ADMINISTRATOR: "Administrador",
            User.Role.DIRECTION: "Direccion",
            User.Role.COORDINATION: "Coordinacion",
            User.Role.TEACHER: "Docente",
        }

        groups = {
            role: Group.objects.get_or_create(name=name)[0]
            for role, name in group_names.items()
        }

        all_permissions = Permission.objects.all()
        groups[User.Role.ADMINISTRATOR].permissions.set(all_permissions)

        view_permissions = Permission.objects.filter(codename__startswith="view_")
        groups[User.Role.DIRECTION].permissions.set(view_permissions)

        coordination_permissions = Permission.objects.filter(
            content_type__app_label__in=["academic", "people", "institutions"],
            codename__regex=r"^(add|change|view)_",
        )
        groups[User.Role.COORDINATION].permissions.set(coordination_permissions)

        teacher_permissions = Permission.objects.filter(
            content_type__app_label="academic",
            codename__regex=r"^(add|change|view)_",
        )
        groups[User.Role.TEACHER].permissions.set(teacher_permissions)

    def create_period(self, institution, options):
        period, _ = AcademicPeriod.objects.get_or_create(
            institution=institution,
            name=options["period_name"],
            defaults={
                "start_date": date.fromisoformat(options["start_date"]),
                "end_date": date.fromisoformat(options["end_date"]),
                "status": AcademicPeriod.Status.ACTIVE,
            },
        )
        return period

    def create_classroom(self, institution, period, options):
        classroom, _ = Classroom.objects.get_or_create(
            institution=institution,
            academic_period=period,
            name=options["classroom_name"],
            section=options["classroom_section"],
            defaults={
                "shift": Classroom.Shift.NIGHT,
                "capacity": 30,
                "is_active": True,
            },
        )
        return classroom

    def create_beta_subjects(self, institution, period):
        subject_specs = [
            ("MAT", "Matematica"),
            ("LEN", "Lengua"),
        ]
        subjects = []

        for code, name in subject_specs:
            subject, _ = Subject.objects.get_or_create(
                institution=institution,
                code=code,
                defaults={"name": name},
            )
            syllabus, _ = Syllabus.objects.get_or_create(
                institution=institution,
                academic_period=period,
                subject=subject,
                name=f"Temario beta {name}",
                defaults={"status": Syllabus.Status.ACTIVE},
            )
            Topic.objects.get_or_create(
                syllabus=syllabus,
                order=1,
                defaults={
                    "title": "Tema inicial",
                    "objective": "Validar el flujo academico completo con contenido minimo.",
                    "class_count": 2,
                    "difficulty": Topic.Difficulty.MEDIUM,
                    "process_question_goal": 10,
                    "final_question_goal": 10,
                },
            )
            subjects.append(subject)

        return subjects

    def assign_admin_user(self, institution, username):
        UserModel = get_user_model()
        try:
            user = UserModel.objects.get(username=username)
        except UserModel.DoesNotExist:
            self.stdout.write(
                self.style.WARNING(
                    f"No existe el usuario {username}; se omitio la asignacion de administrador."
                )
            )
            return

        admin_group = Group.objects.get(name="Administrador")
        user.institution = institution
        user.role = User.Role.ADMINISTRATOR
        user.is_staff = True
        user.is_superuser = True
        user.groups.add(admin_group)
        user.save(update_fields=["institution", "role", "is_staff", "is_superuser", "updated_at"])
