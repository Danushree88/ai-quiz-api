from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.quizzes.views import QuizViewSet, SharedQuizView

router = DefaultRouter()
router.register(r"quizzes", QuizViewSet, basename="quiz")

urlpatterns = [
    path("", include(router.urls)),
    path(
        "quizzes/shared/<uuid:share_token>/",
        SharedQuizView.as_view(),
        name="quiz-shared",
    ),
]