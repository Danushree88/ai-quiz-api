from django.db import models
from django.conf import settings
from django.utils import timezone


class QuizAttempt(models.Model):

    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress", "In Progress"
        COMPLETED = "completed", "Completed"
        EXPIRED = "expired", "Expired"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="attempts",
        db_index=True,
    )
    quiz = models.ForeignKey(
        "quizzes.Quiz",
        on_delete=models.CASCADE,
        related_name="attempts",
        db_index=True,
    )
    status = models.CharField(
        max_length=15, choices=Status.choices, default=Status.IN_PROGRESS
    )
    score = models.FloatField(null=True, blank=True)
    total_correct = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "quiz_attempts"
        indexes = [
            models.Index(fields=["user", "quiz"]),
            models.Index(fields=["user", "status"]),
        ]

    def __str__(self):
        return f"{self.user.email} → {self.quiz.topic} ({self.status})"

    @property
    def is_expired(self):
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False

    def calculate_score(self):
        total = self.answers.count()
        if total == 0:
            return 0.0
        correct = self.answers.filter(is_correct=True).count()
        self.total_correct = correct
        self.score = round((correct / total) * 100, 2)
        self.status = self.Status.COMPLETED
        self.completed_at = timezone.now()
        self.save(update_fields=["score", "total_correct", "status", "completed_at"])
        return self.score


class AttemptAnswer(models.Model):
    attempt = models.ForeignKey(
        QuizAttempt,
        on_delete=models.CASCADE,
        related_name="answers",
        db_index=True,
    )
    question = models.ForeignKey(
        "quizzes.Question",
        on_delete=models.CASCADE,
        db_index=True,
    )
    selected_choice = models.ForeignKey(
        "quizzes.Choice",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    is_correct = models.BooleanField(default=False)
    time_taken_seconds = models.PositiveIntegerField(null=True, blank=True)
    answered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "attempt_answers"
        unique_together = [("attempt", "question")]

    def __str__(self):
        return f"Attempt {self.attempt_id} | Q{self.question_id} | correct={self.is_correct}"