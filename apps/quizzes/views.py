from rest_framework import generics, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.viewsets import ModelViewSet
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from drf_spectacular.utils import extend_schema

from apps.quizzes.models import Quiz
from apps.quizzes.serializers import (
    QuizListSerializer,
    QuizDetailSerializer,
    QuizCreateSerializer,
    QuizStatusSerializer,
    QuestionPublicSerializer,
)
from apps.accounts.permissions import IsOwnerOrAdmin


class QuizViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["difficulty", "status", "is_ai_generated"]
    search_fields = ["topic"]
    ordering_fields = ["created_at", "topic"]
    ordering = ["-created_at"]
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Quiz.objects.none()
        user = self.request.user
        if user.is_admin:
            return Quiz.objects.select_related("created_by").all()
        # Owners see all their quizzes
        # Other users see only READY quizzes (so they can attempt and view leaderboard)
        from django.db.models import Q
        return Quiz.objects.select_related("created_by").filter(
            Q(created_by=user) | Q(status=Quiz.Status.READY)
        )

    def get_serializer_class(self):
        if self.action == "create":
            return QuizCreateSerializer
        if self.action in ["retrieve", "questions"]:
            return QuizDetailSerializer
        if self.action == "quiz_status":
            return QuizStatusSerializer
        return QuizListSerializer

    def create(self, request, *args, **kwargs):
        # Idempotency check
        existing = Quiz.objects.filter(
            created_by=request.user,
            topic__iexact=request.data.get("topic", ""),
            difficulty=request.data.get("difficulty", ""),
            status=Quiz.Status.PENDING,
        ).first()

        if existing:
            return Response(
                {
                    "success": True,
                    "message": "A quiz with this topic and difficulty is already being generated.",
                    "quiz_id": existing.id,
                    "status": existing.status,
                },
                status=status.HTTP_200_OK,
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        quiz = serializer.save()

        from apps.quizzes.tasks import generate_quiz_task
        from django.conf import settings

        if settings.DEBUG:
            # Run synchronously in development
            generate_quiz_task(quiz.id)
        else:
            # Run async via Celery in production
            generate_quiz_task.delay(quiz.id)

        return Response(
            {
                "success": True,
                "message": "Quiz generation started.",
                "quiz_id": quiz.id,
                "status": quiz.status,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["get"], url_path="status")
    def quiz_status(self, request, pk=None):
        quiz = self.get_object()
        return Response({
            "success": True,
            "data": QuizStatusSerializer(quiz).data
        })

    @action(detail=True, methods=["get"], url_path="questions")
    def questions(self, request, pk=None):
        quiz = self.get_object()
        if quiz.status != Quiz.Status.READY:
            return Response(
                {"success": False, "errors": {"detail": "Quiz is not ready yet."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        questions = quiz.questions.prefetch_related("choices").all()
        serializer = QuestionPublicSerializer(questions, many=True)
        return Response({"success": True, "data": serializer.data})

    @action(detail=True, methods=["get"], url_path="leaderboard")
    def leaderboard(self, request, pk=None):
        from apps.attempts.models import QuizAttempt
        from django.core.cache import cache

        quiz = self.get_object()
        cache_key = f"leaderboard_quiz_{quiz.id}"

        # Try cache first
        cached = cache.get(cache_key)
        if cached:
            return Response({"success": True, "data": cached, "cached": True})

        top_attempts = (
            QuizAttempt.objects.filter(
                quiz=quiz,
                status=QuizAttempt.Status.COMPLETED,
                score__isnull=False,
            )
            .select_related("user")
            .order_by("-score", "completed_at")[:10]
        )

        if not top_attempts.exists():
            return Response({
                "success": True,
                "message": "No completed attempts yet.",
                "data": [],
            })

        data = [
            {
                "rank": index + 1,
                "user": attempt.user.email,
                "score": attempt.score,
                "total_correct": attempt.total_correct,
                "completed_at": attempt.completed_at,
            }
            for index, attempt in enumerate(top_attempts)
        ]

        # Cache for 5 minutes
        cache.set(cache_key, data, timeout=300)

        return Response({"success": True, "data": data, "cached": False})


class SharedQuizView(generics.RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = QuestionPublicSerializer
    lookup_field = "share_token"
    queryset = Quiz.objects.all()

    def retrieve(self, request, *args, **kwargs):
        quiz = self.get_object()
        if quiz.status != Quiz.Status.READY:
            return Response(
                {"success": False, "errors": {"detail": "This quiz is not available yet."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        questions = quiz.questions.prefetch_related("choices").all()
        serializer = QuestionPublicSerializer(questions, many=True)
        return Response(
            {
                "success": True,
                "quiz": {
                    "id": quiz.id,
                    "topic": quiz.topic,
                    "difficulty": quiz.difficulty,
                    "time_limit_seconds": quiz.time_limit_seconds,
                },
                "questions": serializer.data,
            }
        )