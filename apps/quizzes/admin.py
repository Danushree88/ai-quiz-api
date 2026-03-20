from django.contrib import admin
from apps.quizzes.models import Quiz, Question, Choice


class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 4


class QuestionInline(admin.StackedInline):
    model = Question
    extra = 1
    show_change_link = True


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ["topic", "difficulty", "status", "is_ai_generated", "created_by", "created_at"]
    list_filter = ["difficulty", "status", "is_ai_generated"]
    search_fields = ["topic", "created_by__email"]
    readonly_fields = ["share_token", "created_at", "updated_at"]
    inlines = [QuestionInline]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ["text", "quiz", "order"]
    search_fields = ["text", "quiz__topic"]
    inlines = [ChoiceInline]


@admin.register(Choice)
class ChoiceAdmin(admin.ModelAdmin):
    list_display = ["text", "question", "is_correct"]
    list_filter = ["is_correct"]