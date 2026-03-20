from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema
from django.db.models import Avg, Count, Q

from apps.attempts.models import QuizAttempt, AttemptAnswer
from apps.analytics.models import UserAnalytics


@extend_schema(responses={200: None})
class GlobalLeaderboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        top_users = (
            UserAnalytics.objects.select_related("user")
            .filter(total_attempts__gt=0)
            .order_by("-avg_score", "-total_attempts")[:10]
        )
        data = [
            {
                "rank": index + 1,
                "user": entry.user.email,
                "avg_score": round(entry.avg_score, 2),
                "total_attempts": entry.total_attempts,
                "total_correct": entry.total_correct,
            }
            for index, entry in enumerate(top_users)
        ]
        return Response({"success": True, "data": data})


@extend_schema(responses={200: None})
class UserAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        analytics, _ = UserAnalytics.objects.get_or_create(user=request.user)

        topic_stats = (
            QuizAttempt.objects.filter(
                user=request.user,
                status=QuizAttempt.Status.COMPLETED,
            )
            .values("quiz__topic")
            .annotate(avg=Avg("score"), attempts=Count("id"))
            .order_by("avg")
        )

        weak_topics = [t["quiz__topic"] for t in topic_stats if t["avg"] < 50]
        strong_topics = [t["quiz__topic"] for t in topic_stats if t["avg"] >= 75]

        return Response({
            "success": True,
            "data": {
                "total_attempts": analytics.total_attempts,
                "avg_score": round(analytics.avg_score, 2),
                "total_correct": analytics.total_correct,
                "total_questions_answered": analytics.total_questions_answered,
                "strong_topics": strong_topics,
                "weak_topics": weak_topics,
            },
        })


@extend_schema(responses={200: None})
class QuizHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        attempts = (
            QuizAttempt.objects.filter(user=request.user)
            .select_related("quiz")
            .order_by("-started_at")
        )
        data = [
            {
                "attempt_id": a.id,
                "quiz_topic": a.quiz.topic,
                "difficulty": a.quiz.difficulty,
                "status": a.status,
                "score": a.score,
                "total_correct": a.total_correct,
                "started_at": a.started_at,
                "completed_at": a.completed_at,
            }
            for a in attempts
        ]
        return Response({"success": True, "data": data})


@extend_schema(responses={200: None})
class QuizAnalyticsView(APIView):
    """
    Per-quiz analytics — only visible to the quiz creator.
    Includes most common wrong answer per question.
    This is the query that justifies using Choice model over JSONField.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, quiz_id):
        from apps.quizzes.models import Quiz, Question

        try:
            quiz = Quiz.objects.get(id=quiz_id, created_by=request.user)
        except Quiz.DoesNotExist:
            return Response(
                {"success": False, "errors": {"detail": "Quiz not found."}},
                status=404,
            )

        total_attempts = QuizAttempt.objects.filter(
            quiz=quiz, status=QuizAttempt.Status.COMPLETED
        ).count()

        avg_score = QuizAttempt.objects.filter(
            quiz=quiz, status=QuizAttempt.Status.COMPLETED
        ).aggregate(avg=Avg("score"))["avg"] or 0.0

        # Per-question breakdown with most common wrong answer
        # This query is ONLY possible because AttemptAnswer has FK to Choice
        questions_data = []
        for question in quiz.questions.prefetch_related("choices").all():
            total_answers = AttemptAnswer.objects.filter(question=question).count()
            correct_answers = AttemptAnswer.objects.filter(
                question=question, is_correct=True
            ).count()

            # Most common wrong choice — your interview talking point
            most_common_wrong = (
                AttemptAnswer.objects.filter(
                    question=question, is_correct=False
                )
                .values("selected_choice__text")
                .annotate(count=Count("id"))
                .order_by("-count")
                .first()
            )

            questions_data.append({
                "question_id": question.id,
                "question_text": question.text,
                "total_answers": total_answers,
                "correct_answers": correct_answers,
                "accuracy_percent": round(
                    (correct_answers / total_answers * 100) if total_answers > 0 else 0, 2
                ),
                "most_common_wrong_answer": (
                    most_common_wrong["selected_choice__text"]
                    if most_common_wrong else None
                ),
            })

        return Response({
            "success": True,
            "data": {
                "quiz_topic": quiz.topic,
                "total_attempts": total_attempts,
                "avg_score": round(avg_score, 2),
                "questions": questions_data,
            },
        })