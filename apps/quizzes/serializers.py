from rest_framework import serializers
from apps.quizzes.models import Quiz, Question, Choice


class ChoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Choice
        fields = ["id", "text", "is_correct"]


class ChoicePublicSerializer(serializers.ModelSerializer):
    """Used during attempt — hides is_correct so user can't cheat."""
    class Meta:
        model = Choice
        fields = ["id", "text"]


class QuestionSerializer(serializers.ModelSerializer):
    choices = ChoiceSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = ["id", "text", "explanation", "order", "choices"]


class QuestionPublicSerializer(serializers.ModelSerializer):
    """Used during attempt — no correct answer revealed."""
    choices = ChoicePublicSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = ["id", "text", "order", "choices"]


class QuizListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list endpoint."""
    created_by = serializers.StringRelatedField()

    class Meta:
        model = Quiz
        fields = [
            "id", "topic", "difficulty", "question_count",
            "status", "is_ai_generated", "time_limit_seconds",
            "created_by", "created_at",
        ]


class QuizDetailSerializer(serializers.ModelSerializer):
    """Full serializer with questions — used after quiz is ready."""
    questions = QuestionSerializer(many=True, read_only=True)
    created_by = serializers.StringRelatedField()

    class Meta:
        model = Quiz
        fields = [
            "id", "topic", "difficulty", "question_count",
            "status", "is_ai_generated", "time_limit_seconds",
            "share_token", "created_by", "created_at", "questions",
        ]


class QuizCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Quiz
        fields = ["id", "topic", "difficulty", "question_count", "time_limit_seconds"]

    def validate_question_count(self, value):
        if value < 1 or value > 20:
            raise serializers.ValidationError("Question count must be between 1 and 20.")
        return value

    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        validated_data["status"] = Quiz.Status.PENDING
        return super().create(validated_data)


class QuizStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Quiz
        fields = ["id", "status"]