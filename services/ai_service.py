import json
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

DIFFICULTY_INSTRUCTIONS = {
    "easy": "Use simple language. Questions should be straightforward with obvious wrong answers.",
    "medium": "Use moderate complexity. Wrong answers should be plausible but clearly incorrect on reflection.",
    "hard": "Use advanced concepts. Wrong answers should be very plausible and require deep knowledge to distinguish.",
}

PROMPT_TEMPLATE = """You are a quiz generator. Generate exactly {num_questions} multiple choice questions about "{topic}".
Difficulty level: {difficulty}. {difficulty_note}

Return ONLY a valid JSON array with no extra text, markdown, or explanation.
Each object must have exactly these fields:
- "text": the question string
- "explanation": a brief explanation of the correct answer (1-2 sentences)
- "choices": an array of exactly 4 objects, each with:
  - "text": the choice string
  - "is_correct": boolean (exactly one must be true)

Example:
[
  {{
    "text": "What is 2 + 2?",
    "explanation": "Basic arithmetic: 2 plus 2 equals 4.",
    "choices": [
      {{"text": "3", "is_correct": false}},
      {{"text": "4", "is_correct": true}},
      {{"text": "5", "is_correct": false}},
      {{"text": "6", "is_correct": false}}
    ]
  }}
]

Generate {num_questions} questions about "{topic}" at {difficulty} difficulty. Return JSON only."""


class AIQuizService:

    @staticmethod
    def generate_quiz(topic: str, difficulty: str, num_questions: int) -> list:
        prompt = AIQuizService._build_prompt(topic, difficulty, num_questions)
        raw_text = AIQuizService._call_api(prompt)
        questions_data = AIQuizService._parse_response(raw_text)
        AIQuizService._validate_response(questions_data, num_questions)
        return questions_data

    @staticmethod
    def _build_prompt(topic: str, difficulty: str, num_questions: int) -> str:
        difficulty_note = DIFFICULTY_INSTRUCTIONS.get(difficulty, "")
        return PROMPT_TEMPLATE.format(
            num_questions=num_questions,
            topic=topic,
            difficulty=difficulty,
            difficulty_note=difficulty_note,
        )

    @staticmethod
    def _call_api(prompt: str) -> str:
        groq_key = getattr(settings, "GROQ_API_KEY", "")
        gemini_key = getattr(settings, "GEMINI_API_KEY", "")

        if groq_key:
            return AIQuizService._call_groq(prompt, groq_key)
        elif gemini_key:
            return AIQuizService._call_gemini(prompt, gemini_key)
        else:
            raise ValueError(
                "No AI API key configured. Set GROQ_API_KEY or GEMINI_API_KEY in .env"
            )


    @staticmethod
    def _call_groq(prompt: str, api_key: str) -> str:
        from groq import Groq
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()

    @staticmethod
    def _call_gemini(prompt: str, api_key: str) -> str:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        # List available models dynamically instead of hardcoding
        available = [
            m.name for m in genai.list_models()
            if "generateContent" in m.supported_generation_methods
        ]
        if not available:
            raise ValueError("No Gemini models available for this API key.")
        # Prefer flash models, fall back to first available
        model_name = next(
            (m for m in available if "flash" in m),
            available[0]
        )
        # Strip "models/" prefix
        model_name = model_name.replace("models/", "")
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(prompt)
        return response.text.strip()

    @staticmethod
    def _parse_response(raw_text: str) -> list:
        # Strip markdown fences if Groq/Gemini wraps in ```json
        if "```" in raw_text:
            lines = raw_text.split("\n")
            raw_text = "\n".join(
                line for line in lines
                if not line.strip().startswith("```")
            )

        try:
            data = json.loads(raw_text.strip())
        except json.JSONDecodeError as e:
            raise ValueError(
                f"AI response was not valid JSON: {e}\nRaw response: {raw_text[:300]}"
            )

        if not isinstance(data, list):
            raise ValueError(
                f"Expected JSON array, got {type(data).__name__}"
            )

        return data

    @staticmethod
    def _validate_response(questions_data: list, expected_count: int) -> None:
        if len(questions_data) == 0:
            raise ValueError("AI returned zero questions.")

        for i, q in enumerate(questions_data):
            if not q.get("text", "").strip():
                raise ValueError(f"Question {i+1} has empty 'text'.")

            choices = q.get("choices", [])
            if not isinstance(choices, list) or len(choices) != 4:
                raise ValueError(
                    f"Question {i+1} must have exactly 4 choices, got {len(choices)}."
                )

            correct_count = sum(1 for c in choices if c.get("is_correct") is True)
            if correct_count != 1:
                raise ValueError(
                    f"Question {i+1} has {correct_count} correct answers, expected exactly 1."
                )

            for j, choice in enumerate(choices):
                if not choice.get("text", "").strip():
                    raise ValueError(
                        f"Question {i+1}, choice {j+1} has empty text."
                    )

        if len(questions_data) < expected_count:
            logger.warning(
                f"AI returned {len(questions_data)} questions, expected {expected_count}."
            )