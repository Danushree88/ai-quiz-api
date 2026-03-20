from django.urls import path
from apps.attempts.views import (
    StartAttemptView,
    SubmitAnswerView,
    SubmitAttemptView,
    AttemptDetailView,
    AttemptQuestionsView,
)

urlpatterns = [
    path("attempts/start/", StartAttemptView.as_view(), name="attempt-start"),
    path("attempts/<int:attempt_id>/questions/", AttemptQuestionsView.as_view(), name="attempt-questions"),
    path("attempts/<int:attempt_id>/answer/", SubmitAnswerView.as_view(), name="attempt-answer"),
    path("attempts/<int:attempt_id>/submit/", SubmitAttemptView.as_view(), name="attempt-submit"),
    path("attempts/<int:pk>/", AttemptDetailView.as_view(), name="attempt-detail"),
]