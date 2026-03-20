from .base import *

DEBUG = True

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# Celery 5+ eager execution — runs tasks synchronously in development
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Override broker so Celery doesn't try to connect to Redis in dev
CELERY_BROKER_URL = "memory://"
CELERY_RESULT_BACKEND = "cache+memory://"