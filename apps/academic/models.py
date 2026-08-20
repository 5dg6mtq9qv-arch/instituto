from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.common.models import SoftDeleteModel, TimeStampedModel


class Subject(SoftDeleteModel):
    institution = models.ForeignKey(
        "institutions.Institution",
        on_delete=models.PROTECT,
        related_name="subjects",
    )
    code = models.CharField(max_length=40)
    name = models.CharField(max_length=160)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["institution", "code"],
                condition=Q(is_deleted=False),
                name="uniq_active_subject_code_by_institution",
            )
        ]

    def __str__(self):
        return self.name


class Syllabus(SoftDeleteModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Borrador"
        ACTIVE = "active", "Activo"
        ARCHIVED = "archived", "Archivado"

    institution = models.ForeignKey(
        "institutions.Institution",
        on_delete=models.PROTECT,
        related_name="syllabuses",
    )
    academic_period = models.ForeignKey(
        "institutions.AcademicPeriod",
        on_delete=models.PROTECT,
        related_name="syllabuses",
        blank=True,
        null=True,
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.PROTECT,
        related_name="syllabuses",
    )
    name = models.CharField(max_length=180)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )

    class Meta:
        ordering = ["subject", "name"]

    def __str__(self):
        return f"{self.subject} - {self.name}"


class Topic(SoftDeleteModel):
    class Difficulty(models.TextChoices):
        BASIC = "basic", "Basica"
        MEDIUM = "medium", "Media"
        ADVANCED = "advanced", "Avanzada"

    syllabus = models.ForeignKey(
        Syllabus,
        on_delete=models.CASCADE,
        related_name="topics",
    )
    title = models.CharField(max_length=180)
    order = models.PositiveIntegerField(default=1)
    objective = models.TextField(blank=True)
    class_count = models.PositiveIntegerField(default=1)
    difficulty = models.CharField(
        max_length=20,
        choices=Difficulty.choices,
        default=Difficulty.MEDIUM,
    )
    process_question_goal = models.PositiveIntegerField(default=10)
    final_question_goal = models.PositiveIntegerField(default=10)

    class Meta:
        ordering = ["syllabus", "order", "title"]
        constraints = [
            models.UniqueConstraint(
                fields=["syllabus", "order"],
                condition=Q(is_deleted=False),
                name="uniq_active_topic_order_by_syllabus",
            )
        ]

    def __str__(self):
        return self.title


class Subtopic(SoftDeleteModel):
    topic = models.ForeignKey(
        Topic,
        on_delete=models.CASCADE,
        related_name="subtopics",
    )
    title = models.CharField(max_length=180)
    order = models.PositiveIntegerField(default=1)
    objective = models.TextField(blank=True)

    class Meta:
        ordering = ["topic", "order", "title"]
        constraints = [
            models.UniqueConstraint(
                fields=["topic", "order"],
                condition=Q(is_deleted=False),
                name="uniq_active_subtopic_order_by_topic",
            )
        ]

    def __str__(self):
        return self.title


class TeachingAssignment(TimeStampedModel):
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="teaching_assignments",
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.PROTECT,
        related_name="teaching_assignments",
    )
    academic_period = models.ForeignKey(
        "institutions.AcademicPeriod",
        on_delete=models.PROTECT,
        related_name="teaching_assignments",
    )
    classroom = models.ForeignKey(
        "institutions.Classroom",
        on_delete=models.PROTECT,
        related_name="teaching_assignments",
        blank=True,
        null=True,
    )
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["academic_period", "subject", "teacher"]
        indexes = [
            models.Index(fields=["teacher", "academic_period", "is_active"]),
        ]

    def __str__(self):
        return f"{self.teacher} - {self.subject}"


class LessonPlan(SoftDeleteModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Borrador"
        SUBMITTED = "submitted", "En revision"
        APPROVED = "approved", "Aprobada"
        REJECTED = "rejected", "Rechazada"
        COMPLETED = "completed", "Completada"

    institution = models.ForeignKey(
        "institutions.Institution",
        on_delete=models.PROTECT,
        related_name="lesson_plans",
    )
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="lesson_plans",
    )
    classroom = models.ForeignKey(
        "institutions.Classroom",
        on_delete=models.PROTECT,
        related_name="lesson_plans",
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.PROTECT,
        related_name="lesson_plans",
    )
    topic = models.ForeignKey(
        Topic,
        on_delete=models.PROTECT,
        related_name="lesson_plans",
    )
    subtopic = models.ForeignKey(
        Subtopic,
        on_delete=models.PROTECT,
        related_name="lesson_plans",
        blank=True,
        null=True,
    )
    class_number = models.PositiveIntegerField(default=1)
    planned_date = models.DateField(db_index=True)
    objective = models.TextField()
    activities = models.TextField()
    expected_resources = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reviewed_lesson_plans",
        blank=True,
        null=True,
    )
    reviewed_at = models.DateTimeField(blank=True, null=True)
    review_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["planned_date", "classroom", "class_number"]
        indexes = [
            models.Index(fields=["teacher", "status"]),
            models.Index(fields=["institution", "planned_date"]),
        ]

    def __str__(self):
        return f"{self.subject} - {self.topic} ({self.planned_date})"


class LearningResource(TimeStampedModel):
    class ResourceType(models.TextChoices):
        DOCUMENT = "document", "Documento"
        VIDEO = "video", "Video"
        LINK = "link", "Enlace"
        SLIDE = "slide", "Diapositiva"
        OTHER = "other", "Otro"

    lesson_plan = models.ForeignKey(
        LessonPlan,
        on_delete=models.CASCADE,
        related_name="resources",
    )
    title = models.CharField(max_length=180)
    resource_type = models.CharField(
        max_length=20,
        choices=ResourceType.choices,
        default=ResourceType.DOCUMENT,
    )
    url = models.URLField(blank=True)
    file = models.FileField(upload_to="academic/resources/", blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="learning_resources",
        blank=True,
        null=True,
    )
    is_ready = models.BooleanField(default=False, db_index=True)

    def __str__(self):
        return self.title


class QuestionBank(SoftDeleteModel):
    class BankType(models.TextChoices):
        PROCESS = "process", "Proceso"
        FINAL = "final", "Simulador/final"

    institution = models.ForeignKey(
        "institutions.Institution",
        on_delete=models.PROTECT,
        related_name="question_banks",
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.PROTECT,
        related_name="question_banks",
    )
    topic = models.ForeignKey(
        Topic,
        on_delete=models.PROTECT,
        related_name="question_banks",
        blank=True,
        null=True,
    )
    subtopic = models.ForeignKey(
        Subtopic,
        on_delete=models.PROTECT,
        related_name="question_banks",
        blank=True,
        null=True,
    )
    bank_type = models.CharField(max_length=20, choices=BankType.choices)
    target_questions = models.PositiveIntegerField(default=10)
    reviewed_by_coordination = models.BooleanField(default=False, db_index=True)

    class Meta:
        ordering = ["subject", "topic", "bank_type"]
        indexes = [
            models.Index(fields=["institution", "bank_type"]),
            models.Index(fields=["subject", "topic", "subtopic"]),
        ]

    def __str__(self):
        return f"{self.subject} - {self.get_bank_type_display()}"


class Question(SoftDeleteModel):
    class Difficulty(models.TextChoices):
        EASY = "easy", "Facil"
        MEDIUM = "medium", "Media"
        HARD = "hard", "Dificil"

    class Status(models.TextChoices):
        DRAFT = "draft", "Borrador"
        IN_REVIEW = "in_review", "En revision"
        APPROVED = "approved", "Aprobada"
        REJECTED = "rejected", "Rechazada"

    question_bank = models.ForeignKey(
        QuestionBank,
        on_delete=models.PROTECT,
        related_name="questions",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_questions",
    )
    prompt = models.TextField()
    answers = models.JSONField(default=list, blank=True)
    correct_answer = models.TextField(blank=True)
    explanation = models.TextField(blank=True)
    difficulty = models.CharField(
        max_length=20,
        choices=Difficulty.choices,
        default=Difficulty.MEDIUM,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reviewed_questions",
        blank=True,
        null=True,
    )
    reviewed_at = models.DateTimeField(blank=True, null=True)
    review_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["question_bank", "-created_at"]
        indexes = [
            models.Index(fields=["created_by", "status"]),
        ]

    def __str__(self):
        return self.prompt[:80]


class AttendanceRecord(TimeStampedModel):
    class Status(models.TextChoices):
        PRESENT = "present", "Presente"
        ABSENT = "absent", "Ausente"
        LATE = "late", "Atraso"
        EXCUSED = "excused", "Justificado"

    lesson_plan = models.ForeignKey(
        LessonPlan,
        on_delete=models.CASCADE,
        related_name="attendance_records",
    )
    student = models.ForeignKey(
        "people.Student",
        on_delete=models.PROTECT,
        related_name="attendance_records",
    )
    status = models.CharField(max_length=20, choices=Status.choices)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="attendance_records",
        blank=True,
        null=True,
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["lesson_plan", "student"]
        constraints = [
            models.UniqueConstraint(
                fields=["lesson_plan", "student"],
                name="uniq_attendance_by_lesson_student",
            )
        ]

    def __str__(self):
        return f"{self.student} - {self.get_status_display()}"


class Evaluation(TimeStampedModel):
    class EvaluationType(models.TextChoices):
        PROCESS = "process", "Proceso"
        FINAL = "final", "Final"
        SIMULATOR = "simulator", "Simulador"

    lesson_plan = models.ForeignKey(
        LessonPlan,
        on_delete=models.PROTECT,
        related_name="evaluations",
        blank=True,
        null=True,
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.PROTECT,
        related_name="evaluations",
    )
    topic = models.ForeignKey(
        Topic,
        on_delete=models.PROTECT,
        related_name="evaluations",
        blank=True,
        null=True,
    )
    title = models.CharField(max_length=180)
    evaluation_type = models.CharField(
        max_length=20,
        choices=EvaluationType.choices,
        default=EvaluationType.PROCESS,
    )
    date = models.DateField(db_index=True)
    max_score = models.DecimalField(max_digits=5, decimal_places=2, default=10)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="evaluations",
        blank=True,
        null=True,
    )

    class Meta:
        ordering = ["-date", "subject"]

    def __str__(self):
        return self.title


class StudentEvaluationResult(TimeStampedModel):
    evaluation = models.ForeignKey(
        Evaluation,
        on_delete=models.CASCADE,
        related_name="results",
    )
    student = models.ForeignKey(
        "people.Student",
        on_delete=models.PROTECT,
        related_name="evaluation_results",
    )
    score = models.DecimalField(max_digits=5, decimal_places=2)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["evaluation", "student"]
        constraints = [
            models.UniqueConstraint(
                fields=["evaluation", "student"],
                name="uniq_result_by_evaluation_student",
            )
        ]

    def __str__(self):
        return f"{self.student} - {self.score}"

# Create your models here.
