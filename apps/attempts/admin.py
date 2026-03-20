from django.contrib import admin
from apps.attempts.models import QuizAttempt, AttemptAnswer


class AttemptAnswerInline(admin.TabularInline):
    model = AttemptAnswer
    extra = 0
    readonly_fields = ["question", "selected_choice", "is_correct", "time_taken_seconds"]


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ["user", "quiz", "status", "score", "started_at", "completed_at"]
    list_filter = ["status"]
    search_fields = ["user__email", "quiz__topic"]
    readonly_fields = ["started_at", "completed_at", "expires_at"]
    inlines = [AttemptAnswerInline]


@admin.register(AttemptAnswer)
class AttemptAnswerAdmin(admin.ModelAdmin):
    list_display = ["attempt", "question", "selected_choice", "is_correct"]
    list_filter = ["is_correct"]