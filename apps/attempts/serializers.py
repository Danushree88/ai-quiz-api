from rest_framework import serializers
from django.utils import timezone
from apps.attempts.models import QuizAttempt, AttemptAnswer
from apps.quizzes.models import Quiz, Choice


class StartAttemptSerializer(serializers.Serializer):
    quiz_id = serializers.IntegerField()

    def validate_quiz_id(self, value):
        try:
            quiz = Quiz.objects.get(id=value)
        except Quiz.DoesNotExist:
            raise serializers.ValidationError("Quiz not found.")
        if quiz.status != Quiz.Status.READY:
            raise serializers.ValidationError("Quiz is not ready yet.")
        return value

    def create(self, validated_data):
        user = self.context["request"].user
        quiz = Quiz.objects.get(id=validated_data["quiz_id"])

        # Check for existing in-progress attempt
        existing = QuizAttempt.objects.filter(
            user=user, quiz=quiz, status=QuizAttempt.Status.IN_PROGRESS
        ).first()
        if existing:
            return existing

        attempt = QuizAttempt(user=user, quiz=quiz)

        # Set expiry if quiz has a time limit
        if quiz.time_limit_seconds:
            attempt.expires_at = timezone.now() + timezone.timedelta(
                seconds=quiz.time_limit_seconds
            )

        attempt.save()
        return attempt


class SubmitAnswerSerializer(serializers.Serializer):
    question_id = serializers.IntegerField()
    choice_id = serializers.IntegerField()
    time_taken_seconds = serializers.IntegerField(required=False, allow_null=True)

    def validate(self, attrs):
        attempt = self.context["attempt"]

        # Check expiry
        if attempt.is_expired:
            raise serializers.ValidationError(
                {"detail": "This attempt has expired."}
            )

        # Validate question belongs to this quiz
        if not attempt.quiz.questions.filter(id=attrs["question_id"]).exists():
            raise serializers.ValidationError(
                {"question_id": "This question does not belong to this quiz."}
            )

        # Validate choice belongs to this question
        try:
            choice = Choice.objects.get(
                id=attrs["choice_id"], question_id=attrs["question_id"]
            )
        except Choice.DoesNotExist:
            raise serializers.ValidationError(
                {"choice_id": "This choice does not belong to this question."}
            )

        attrs["choice"] = choice
        return attrs


class AttemptAnswerSerializer(serializers.ModelSerializer):
    question_text = serializers.CharField(source="question.text", read_only=True)
    selected_choice_text = serializers.CharField(
        source="selected_choice.text", read_only=True
    )

    class Meta:
        model = AttemptAnswer
        fields = [
            "id", "question_id", "question_text",
            "selected_choice_id", "selected_choice_text",
            "is_correct", "time_taken_seconds",
        ]


class QuizAttemptSerializer(serializers.ModelSerializer):
    answers = AttemptAnswerSerializer(many=True, read_only=True)
    quiz_topic = serializers.CharField(source="quiz.topic", read_only=True)

    class Meta:
        model = QuizAttempt
        fields = [
            "id", "quiz_id", "quiz_topic", "status", "score",
            "total_correct", "started_at", "completed_at",
            "expires_at", "answers",
        ]