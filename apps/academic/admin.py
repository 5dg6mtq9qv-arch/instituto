from django.contrib import admin

from .models import (
    AttendanceRecord,
    Evaluation,
    LearningResource,
    LessonPlan,
    Question,
    QuestionBank,
    StudentEvaluationResult,
    Subject,
    Subtopic,
    Syllabus,
    TeachingAssignment,
    Topic,
)


class SubtopicInline(admin.TabularInline):
    model = Subtopic
    extra = 0


class LearningResourceInline(admin.TabularInline):
    model = LearningResource
    extra = 0


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "institution", "is_active", "is_deleted")
    list_filter = ("institution", "is_active", "is_deleted")
    search_fields = ("code", "name")


@admin.register(Syllabus)
class SyllabusAdmin(admin.ModelAdmin):
    list_display = ("name", "subject", "academic_period", "status")
    list_filter = ("institution", "subject", "status")
    search_fields = ("name", "subject__name")


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ("title", "syllabus", "order", "difficulty", "class_count", "process_question_goal", "final_question_goal")
    list_filter = ("syllabus__subject", "difficulty")
    search_fields = ("title", "syllabus__name", "syllabus__subject__name")
    inlines = [SubtopicInline]


@admin.register(Subtopic)
class SubtopicAdmin(admin.ModelAdmin):
    list_display = ("title", "topic", "order")
    list_filter = ("topic__syllabus__subject",)
    search_fields = ("title", "topic__title")


@admin.register(TeachingAssignment)
class TeachingAssignmentAdmin(admin.ModelAdmin):
    list_display = ("teacher", "subject", "academic_period", "classroom", "is_active")
    list_filter = ("academic_period", "subject", "is_active")
    search_fields = ("teacher__username", "teacher__first_name", "teacher__last_name", "subject__name")


@admin.register(LessonPlan)
class LessonPlanAdmin(admin.ModelAdmin):
    list_display = ("subject", "topic", "teacher", "classroom", "planned_date", "status")
    list_filter = ("institution", "subject", "status", "planned_date")
    search_fields = ("teacher__username", "subject__name", "topic__title", "objective")
    date_hierarchy = "planned_date"
    inlines = [LearningResourceInline]


@admin.register(LearningResource)
class LearningResourceAdmin(admin.ModelAdmin):
    list_display = ("title", "lesson_plan", "resource_type", "is_ready", "created_by")
    list_filter = ("resource_type", "is_ready")
    search_fields = ("title", "lesson_plan__topic__title")


@admin.register(QuestionBank)
class QuestionBankAdmin(admin.ModelAdmin):
    list_display = ("subject", "topic", "subtopic", "bank_type", "target_questions", "reviewed_by_coordination")
    list_filter = ("institution", "subject", "bank_type", "reviewed_by_coordination")
    search_fields = ("subject__name", "topic__title", "subtopic__title")


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("question_bank", "created_by", "difficulty", "status", "created_at")
    list_filter = ("question_bank__subject", "question_bank__bank_type", "difficulty", "status")
    search_fields = ("prompt", "created_by__username", "created_by__first_name", "created_by__last_name")


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ("lesson_plan", "student", "status", "recorded_by")
    list_filter = ("status", "lesson_plan__planned_date")
    search_fields = ("student__first_names", "student__last_names", "lesson_plan__topic__title")


class StudentEvaluationResultInline(admin.TabularInline):
    model = StudentEvaluationResult
    extra = 0


@admin.register(Evaluation)
class EvaluationAdmin(admin.ModelAdmin):
    list_display = ("title", "subject", "topic", "evaluation_type", "date", "max_score")
    list_filter = ("subject", "evaluation_type", "date")
    search_fields = ("title", "subject__name", "topic__title")
    date_hierarchy = "date"
    inlines = [StudentEvaluationResultInline]


@admin.register(StudentEvaluationResult)
class StudentEvaluationResultAdmin(admin.ModelAdmin):
    list_display = ("evaluation", "student", "score")
    list_filter = ("evaluation__subject",)
    search_fields = ("student__first_names", "student__last_names", "evaluation__title")

# Register your models here.
