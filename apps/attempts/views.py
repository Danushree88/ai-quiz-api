from rest_framework import status, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema
from apps.quizzes.models import Quiz
from apps.attempts.models import QuizAttempt, AttemptAnswer
from apps.attempts.serializers import (
    StartAttemptSerializer,
    SubmitAnswerSerializer,
    QuizAttemptSerializer,
)


@extend_schema(request=StartAttemptSerializer, responses={201: QuizAttemptSerializer})
class StartAttemptView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = StartAttemptSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        attempt = serializer.save()
        return Response(
            {
                "success": True,
                "message": "Attempt started.",
                "attempt_id": attempt.id,
                "expires_at": attempt.expires_at,
            },
            status=status.HTTP_201_CREATED,
        )


@extend_schema(request=SubmitAnswerSerializer, responses={200: None})
class SubmitAnswerView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, attempt_id):
        try:
            attempt = QuizAttempt.objects.get(
                id=attempt_id, user=request.user
            )
        except QuizAttempt.DoesNotExist:
            return Response(
                {"success": False, "errors": {"detail": "Attempt not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )

        if attempt.status != QuizAttempt.Status.IN_PROGRESS:
            return Response(
                {"success": False, "errors": {"detail": "This attempt is already completed or expired."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if attempt.is_expired:
            attempt.status = QuizAttempt.Status.EXPIRED
            attempt.save(update_fields=["status"])
            return Response(
                {"success": False, "errors": {"detail": "This attempt has expired."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = SubmitAnswerSerializer(
            data=request.data, context={"attempt": attempt}
        )
        serializer.is_valid(raise_exception=True)

        choice = serializer.validated_data["choice"]
        question_id = serializer.validated_data["question_id"]
        time_taken = serializer.validated_data.get("time_taken_seconds")

        answer, created = AttemptAnswer.objects.update_or_create(
            attempt=attempt,
            question_id=question_id,
            defaults={
                "selected_choice": choice,
                "is_correct": choice.is_correct,
                "time_taken_seconds": time_taken,
            },
        )

        return Response(
            {
                "success": True,
                "is_correct": answer.is_correct,
                "message": "Answer saved." if created else "Answer updated.",
            }
        )


@extend_schema(responses={200: QuizAttemptSerializer})
class SubmitAttemptView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, attempt_id):
        try:
            attempt = QuizAttempt.objects.get(
                id=attempt_id, user=request.user
            )
        except QuizAttempt.DoesNotExist:
            return Response(
                {"success": False, "errors": {"detail": "Attempt not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )

        if attempt.status != QuizAttempt.Status.IN_PROGRESS:
            return Response(
                {"success": False, "errors": {"detail": "This attempt is already completed or expired."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        score = attempt.calculate_score()
        _update_user_analytics(attempt)

        serializer = QuizAttemptSerializer(attempt)
        return Response(
            {
                "success": True,
                "message": "Quiz submitted successfully.",
                "score": score,
                "data": serializer.data,
            }
        )


class AttemptDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = QuizAttemptSerializer

    def get_queryset(self):
        return QuizAttempt.objects.filter(
            user=self.request.user
        ).prefetch_related("answers__question", "answers__selected_choice")


def _update_user_analytics(attempt):
    from apps.analytics.models import UserAnalytics
    from django.db.models import Avg
    from django.core.cache import cache

    analytics, _ = UserAnalytics.objects.get_or_create(user=attempt.user)
    all_attempts = QuizAttempt.objects.filter(
        user=attempt.user, status=QuizAttempt.Status.COMPLETED
    )
    analytics.total_attempts = all_attempts.count()
    analytics.avg_score = all_attempts.aggregate(Avg("score"))["score__avg"] or 0.0
    analytics.total_correct += attempt.total_correct
    analytics.total_questions_answered += attempt.answers.count()
    analytics.save()

    # Invalidate leaderboard cache for this quiz when new score submitted
    cache_key = f"leaderboard_quiz_{attempt.quiz_id}"
    cache.delete(cache_key)
    
class AttemptQuestionsView(APIView):
    """
    Returns all questions with choice IDs for an active attempt.
    This is what the frontend calls to show the quiz to the user.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, attempt_id):
        try:
            attempt = QuizAttempt.objects.select_related("quiz").get(
                id=attempt_id, user=request.user
            )
        except QuizAttempt.DoesNotExist:
            return Response(
                {"success": False, "errors": {"detail": "Attempt not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )

        if attempt.is_expired:
            attempt.status = QuizAttempt.Status.EXPIRED
            attempt.save(update_fields=["status"])
            return Response(
                {"success": False, "errors": {"detail": "This attempt has expired."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        questions = attempt.quiz.questions.prefetch_related("choices").order_by("order")

        # Also show which questions have already been answered
        answered = {
            a.question_id: a.selected_choice_id
            for a in attempt.answers.all()
        }

        data = []
        for q in questions:
            data.append({
                "question_id": q.id,
                "question_text": q.text,
                "order": q.order,
                "already_answered": q.id in answered,
                "choices": [
                    {
                        "choice_id": c.id,
                        "choice_text": c.text,
                    }
                    for c in q.choices.all()
                ],
            })

        return Response({
            "success": True,
            "attempt_id": attempt.id,
            "quiz_topic": attempt.quiz.topic,
            "quiz_difficulty": attempt.quiz.difficulty,
            "time_limit_seconds": attempt.quiz.time_limit_seconds,
            "expires_at": attempt.expires_at,
            "total_questions": len(data),
            "questions_answered": len(answered),
            "data": data,
        })