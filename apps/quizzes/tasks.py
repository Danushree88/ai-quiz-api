from celery import shared_task
from django.utils import timezone


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=60,
    max_retries=3,
)
def generate_quiz_task(self, quiz_id):
    from apps.quizzes.models import Quiz, Question, Choice
    from services.ai_service import AIQuizService

    try:
        quiz = Quiz.objects.get(id=quiz_id)
    except Quiz.DoesNotExist:
        return

    try:
        questions_data = AIQuizService.generate_quiz(
            topic=quiz.topic,
            difficulty=quiz.difficulty,
            num_questions=quiz.question_count,
        )

        # Save questions and choices to DB
        for index, q_data in enumerate(questions_data):
            question = Question.objects.create(
                quiz=quiz,
                text=q_data["text"],
                explanation=q_data.get("explanation", ""),
                order=index + 1,
            )
            for choice_data in q_data["choices"]:
                Choice.objects.create(
                    question=question,
                    text=choice_data["text"],
                    is_correct=choice_data["is_correct"],
                )

        quiz.status = Quiz.Status.READY
        quiz.save(update_fields=["status", "updated_at"])

    except Exception as exc:
        # On final retry failure — mark as failed and use fallback
        if self.request.retries == self.max_retries:
            _save_fallback_questions(quiz)
        raise exc


def _save_fallback_questions(quiz):
    """Used when AI fails after all retries."""
    from apps.quizzes.models import Question, Choice

    fallback = [
        {
            "text": f"Sample question about {quiz.topic} (1)",
            "explanation": "This is a fallback question.",
            "choices": [
                {"text": "Option A", "is_correct": True},
                {"text": "Option B", "is_correct": False},
                {"text": "Option C", "is_correct": False},
                {"text": "Option D", "is_correct": False},
            ],
        },
        {
            "text": f"Sample question about {quiz.topic} (2)",
            "explanation": "This is a fallback question.",
            "choices": [
                {"text": "Option A", "is_correct": False},
                {"text": "Option B", "is_correct": True},
                {"text": "Option C", "is_correct": False},
                {"text": "Option D", "is_correct": False},
            ],
        },
    ]

    for index, q_data in enumerate(fallback):
        question = Question.objects.create(
            quiz=quiz,
            text=q_data["text"],
            explanation=q_data["explanation"],
            order=index + 1,
        )
        for choice_data in q_data["choices"]:
            Choice.objects.create(
                question=question,
                text=choice_data["text"],
                is_correct=choice_data["is_correct"],
            )

    quiz.status = Quiz.Status.READY
    quiz.save(update_fields=["status", "updated_at"])