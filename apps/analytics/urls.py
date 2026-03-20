from django.urls import path
from apps.analytics.views import (
    GlobalLeaderboardView,
    UserAnalyticsView,
    QuizHistoryView,
    QuizAnalyticsView,
)

urlpatterns = [
    path("leaderboard/", GlobalLeaderboardView.as_view(), name="global-leaderboard"),
    path("analytics/me/", UserAnalyticsView.as_view(), name="user-analytics"),
    path("analytics/quiz/<int:quiz_id>/", QuizAnalyticsView.as_view(), name="quiz-analytics"),
    path("history/", QuizHistoryView.as_view(), name="quiz-history"),
]