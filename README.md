# AI-Powered Quiz API

A production-grade REST API for a quiz application built with Django and Django REST Framework. Features AI-generated questions using Groq (Llama 3.3 70B), async task processing via Celery, JWT authentication, Redis caching, and detailed analytics.

**Live API:** https://ai-quiz-api-production.up.railway.app  
**Swagger Docs:** https://ai-quiz-api-production.up.railway.app/api/docs/  
**GitHub:** https://github.com/Danushree88/ai-quiz-api

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Framework | Django 6, Django REST Framework |
| Database | PostgreSQL |
| Cache | Redis (locmem in development) |
| Async Tasks | Celery |
| AI Provider | Groq — Llama 3.3 70B (Gemini fallback) |
| Authentication | JWT via djangorestframework-simplejwt |
| API Docs | Swagger UI via drf-spectacular |
| Deployment | Railway |

---

## Local Setup

### Prerequisites
- Python 3.12
- PostgreSQL running locally
- Git

### Steps

```bash
git clone https://github.com/Danushree88/ai-quiz-api.git
cd ai-quiz-api

python -m venv venv
venv\Scripts\activate        # Windows PowerShell
source venv/bin/activate     # Mac/Linux

pip install -r requirements.txt
```

Create a `.env` file in the project root:

```env
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

DB_NAME=quiz_db
DB_USER=postgres
DB_PASSWORD=yourpassword
DB_HOST=localhost
DB_PORT=5432

REDIS_URL=redis://localhost:6379/0
GROQ_API_KEY=your-groq-api-key
GEMINI_API_KEY=
```

Get a free Groq API key at https://console.groq.com

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Visit `http://127.0.0.1:8000/api/docs/` for the Swagger UI.

> Redis is optional in development. The app automatically falls back to Django's in-memory cache when Redis is not running.

---

## Project Structure

```
quiz_api/
├── apps/
│   ├── accounts/       # Custom User model, JWT auth, permissions
│   ├── quizzes/        # Quiz, Question, Choice models + Celery task
│   ├── attempts/       # QuizAttempt, AttemptAnswer, scoring
│   ├── analytics/      # UserAnalytics, leaderboard, history
│   └── core/           # Global exception handler
├── services/
│   └── ai_service.py   # Groq/Gemini integration + validation layer
├── config/
│   ├── settings/
│   │   ├── base.py         # Shared settings
│   │   ├── development.py  # Local dev overrides
│   │   └── production.py   # Production overrides
│   ├── celery.py
│   └── urls.py
├── requirements.txt
└── railway.toml
```

---

## Database Schema

### Models and Relationships

```
User (custom — extends AbstractUser)
  ├── email (unique, used as USERNAME_FIELD)
  └── role (admin / user)

Quiz
  ├── topic, difficulty, question_count
  ├── status (pending / ready / failed)
  ├── is_ai_generated
  ├── time_limit_seconds    ← timed quiz support
  ├── share_token (UUID)    ← quiz sharing
  └── created_by → User

Question
  ├── quiz → Quiz
  └── text, explanation, order

Choice
  ├── question → Question
  ├── text
  └── is_correct (bool)
      DB constraint: exactly 1 correct per question

QuizAttempt
  ├── user → User
  ├── quiz → Quiz
  ├── status (in_progress / completed / expired)
  ├── score, total_correct
  └── expires_at    ← set when quiz has time_limit

AttemptAnswer
  ├── attempt → QuizAttempt
  ├── question → Question
  ├── selected_choice → Choice   ← real FK, not a stored string
  ├── is_correct
  └── time_taken_seconds

UserAnalytics (one-to-one with User)
  ├── total_attempts, total_correct
  ├── total_questions_answered
  └── avg_score
```

### Key Design Decision — Choice Model vs JSONField

Options for quiz questions could have been stored as a JSONField array on the Question model. Instead, each option is a separate `Choice` row with a real foreign key.

`AttemptAnswer.selected_choice` is a FK to `Choice`, not a stored string. This enables the query:

```python
# Most common wrong answer per question
AttemptAnswer.objects.filter(question=q, is_correct=False)
    .values("selected_choice__text")
    .annotate(count=Count("id"))
    .order_by("-count")
    .first()
```

This identifies which wrong option most users pick — useful for detecting misleading questions. This query is impossible to do efficiently with JSONField without parsing every row in Python.

A `UniqueConstraint` with `condition=Q(is_correct=True)` also enforces exactly one correct answer per question at the database level.

### Indexes

```python
# Quiz — fast filtering by owner and generation status
models.Index(fields=["created_by", "status"])
models.Index(fields=["topic", "difficulty"])

# QuizAttempt — fast lookups for history and leaderboard queries
models.Index(fields=["user", "quiz"])
models.Index(fields=["user", "status"])
```

---

## API Endpoints

All endpoints versioned under `/api/v1/`. Full interactive docs at `/api/docs/`.

### Authentication
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/auth/register/` | None | Register, returns JWT tokens |
| POST | `/auth/login/` | None | Login, returns JWT tokens |
| POST | `/auth/logout/` | Required | Blacklist refresh token |
| POST | `/auth/token/refresh/` | None | Get new access token |
| GET/PATCH | `/auth/profile/` | Required | View or update profile |

### Quizzes
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/quizzes/` | Required | Create quiz + trigger AI generation |
| GET | `/quizzes/` | Required | List quizzes (filter by difficulty, status) |
| GET | `/quizzes/{id}/` | Required | Quiz detail |
| GET | `/quizzes/{id}/status/` | Required | Poll generation status |
| GET | `/quizzes/{id}/questions/` | Required | Questions without correct answers |
| GET | `/quizzes/{id}/leaderboard/` | Required | Top 10 scores for this quiz (cached) |
| GET | `/quizzes/shared/{token}/` | None | Public access via share token |

### Attempts
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/attempts/start/` | Required | Start attempt, returns attempt_id |
| GET | `/attempts/{id}/questions/` | Required | Questions + choice IDs for this attempt |
| POST | `/attempts/{id}/answer/` | Required | Submit one answer |
| POST | `/attempts/{id}/submit/` | Required | Finish attempt, returns score |
| GET | `/attempts/{id}/` | Required | Full attempt detail with all answers |

### Analytics
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/analytics/me/` | Required | Personal stats + strong/weak topics |
| GET | `/analytics/quiz/{id}/` | Required | Per-quiz breakdown + most common wrong answers |
| GET | `/history/` | Required | Past attempts with scores |
| GET | `/leaderboard/` | Required | Global top 10 users by avg score |

---

## Quiz Generation Flow

```
POST /api/v1/quizzes/
        │
        ▼
Idempotency check:
  Already a pending quiz for this user + topic + difficulty?
  YES → return existing quiz_id (no duplicate AI call)
  NO  → create Quiz (status = pending)
        │
        ▼
In DEBUG mode:  generate_quiz_task(quiz.id)        ← synchronous
In production:  generate_quiz_task.delay(quiz.id)  ← async via Celery

API returns immediately:
{ "quiz_id": 1, "status": "pending" }
        │
        ▼ (background Celery worker)
1. Call AIQuizService.generate_quiz(topic, difficulty, count)
2. validate_ai_response() — checks question count, 4 choices, 1 correct answer
3. Save questions + choices to DB
4. quiz.status = "ready"

On failure:
  Retry up to 3 times with exponential backoff (max 60s)
  Final failure → save fallback questions → status = "ready"
        │
        ▼
Client polls: GET /api/v1/quizzes/{id}/status/
Until: { "status": "ready" }
```

**Why async?** Groq/Gemini calls take 5–10 seconds. Blocking the request thread wastes server resources and creates poor UX. With Celery the API responds in under 100ms regardless of AI latency.

**Future improvement:** Replace polling with Server-Sent Events to push the `quiz_ready` event. Backend logic stays identical — only the transport changes.

---

## AI Integration

### Service Layer

All AI logic is isolated in `services/ai_service.py`. Views never call the AI provider directly. This separation means:
- Swapping providers (Groq → Gemini → OpenAI) requires changing one file
- Easy to mock in tests
- Single place for retry logic, validation, and prompt engineering

### Provider Strategy

```python
def _call_api(prompt):
    if groq_key:
        return _call_groq(prompt, groq_key)      # Primary: Llama 3.3 70B
    elif gemini_key:
        return _call_gemini(prompt, gemini_key)  # Fallback: Gemini flash
    else:
        raise ValueError("No AI API key configured")
```

### Validation Layer

AI output is non-deterministic. Every response is validated before saving to the database:

```python
def _validate_response(questions_data, expected_count):
    for i, q in enumerate(questions_data):
        if not q.get("text", "").strip():
            raise ValueError(f"Question {i+1} has empty text")
        if len(q["choices"]) != 4:
            raise ValueError(f"Question {i+1} must have exactly 4 choices")
        correct_count = sum(1 for c in q["choices"] if c.get("is_correct"))
        if correct_count != 1:
            raise ValueError(f"Question {i+1} has {correct_count} correct answers")
```

Without this, a malformed AI response would silently write corrupt quiz data to the database.

### Idempotent Generation

Before queuing a Celery task, the view checks if the user already has a pending quiz for the same topic and difficulty. If yes, the existing `quiz_id` is returned. This prevents duplicate AI calls from double-clicks and network retries, saving API quota.

---

## Caching Strategy

The leaderboard is read frequently but changes only when a new attempt is submitted — a perfect candidate for caching.

```python
# Read path: cache first
cache_key = f"leaderboard_quiz_{quiz.id}"
cached = cache.get(cache_key)
if cached:
    return Response({"data": cached, "cached": True})

# Cache miss: query DB, store for 5 minutes
cache.set(cache_key, data, timeout=300)
```

```python
# Invalidation: when a new score is submitted
cache.delete(f"leaderboard_quiz_{attempt.quiz_id}")
```

Cache backend switches automatically based on environment:
- **Development:** Django `LocMemCache`
- **Production:** `django-redis` when `REDIS_URL` is set

---

## Security

- **JWT auth** — 24hr access token, 7-day refresh token
- **Token blacklisting** on logout via `rest_framework_simplejwt.token_blacklist`
- **Role-based access** — admins see all quizzes; regular users see their own + all ready quizzes
- **Custom permission classes** — `IsAdminUser`, `IsOwnerOrAdmin`
- **Input validation** on every serializer before any database write
- **Rate limiting** — 1000 requests/day per user, 100/day anonymous, 10 AI generations/hour
- **Timed quiz enforcement** — expiry is checked server-side on every answer submission, not client-side

---

## Bonus Features

### Timed Quizzes
Quizzes support an optional `time_limit_seconds`. On attempt start, `expires_at = started_at + timedelta(seconds=time_limit)` is stored. Every answer submission checks this server-side — the timer cannot be bypassed by the client.

### Quiz Sharing
Every quiz has a UUID `share_token` generated at creation. `GET /quizzes/shared/{token}/` is a public endpoint — no authentication required — returning questions without correct answers. Attempting the quiz and appearing on the leaderboard requires an account, preserving score integrity.

### Analytics
Quiz creators can view per-question accuracy and the most commonly selected wrong answer. This query is only possible because `AttemptAnswer` stores a FK to `Choice` rather than a raw string.

---

## Design Trade-offs

| Decision | Chosen | Alternative | Reason |
|----------|--------|-------------|--------|
| Choice storage | Separate FK model | JSONField | Enables per-choice analytics and relational integrity |
| AI calls | Async via Celery | Synchronous in view | Non-blocking, retryable, better UX |
| Auth | JWT (stateless) | Session auth | Supports horizontal scaling without shared session store |
| Leaderboard | Redis cache | Always query DB | Eliminates DB load on high-read endpoint |
| Share feature | UUID field on Quiz | Separate ShareLink model | Simpler, sufficient for current needs |
| Settings | Split base/dev/prod | Single settings.py | Clean environment-specific config |

---

## Scaling Strategy

1. **Stateless Django workers** — JWT means no server-side sessions; scale behind a load balancer immediately
2. **Independent Celery scaling** — AI workers scale separately from API workers based on queue depth
3. **PostgreSQL read replica** — analytics aggregation queries go to replica; writes go to primary
4. **Leaderboard in Redis** — already implemented; eliminates DB queries for the most-read endpoint
5. **DB connection pooling** — add PgBouncer between Django and PostgreSQL under high concurrency
6. **Separate analytics store** — move `UserAnalytics` aggregations to ClickHouse as write volume grows
7. **CDN for static files** — move to S3 + CloudFront; whitenoise handles current scale

---

## Challenges and Solutions

**Celery eager mode in development** — `CELERY_TASK_ALWAYS_EAGER` is unreliable in Celery 5+. Solved by checking `settings.DEBUG` in the view and calling the task directly vs `.delay()` based on environment.

**Gemini API quota and model names** — Free tier quota exhausted quickly and model names changed between API versions. Switched primary provider to Groq (completely free, faster) with Gemini as fallback using dynamic model discovery via `genai.list_models()`.

**Railway build failures** — `migrate` failed during Docker build phase because the database is only accessible at runtime. Fixed by keeping `migrate` in the start command in `railway.toml`, not in the build command.

**Static files 404 in production** — `staticfiles/` was in `.gitignore` so whitenoise had nothing to serve. Fixed by removing `staticfiles/` from `.gitignore` and committing the collected files.

---

## Admin Interface

Django admin available at `/admin/` with management of:
- Users — list by role, search by email
- Quizzes — with inline Questions
- Questions — with inline Choices
- Quiz Attempts — with inline Answers
- User Analytics

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_KEY` | Yes | Django secret key |
| `DEBUG` | Yes | `True` for development, `False` for production |
| `ALLOWED_HOSTS` | Yes | Comma-separated allowed hostnames |
| `DATABASE_URL` | Production | Full PostgreSQL URL (auto-set by Railway) |
| `DB_NAME` | Development | PostgreSQL database name |
| `DB_USER` | Development | PostgreSQL username |
| `DB_PASSWORD` | Development | PostgreSQL password |
| `GROQ_API_KEY` | Yes | Free at console.groq.com |
| `GEMINI_API_KEY` | No | Fallback AI provider |
| `REDIS_URL` | Production | Redis connection URL |
