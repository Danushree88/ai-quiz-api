import os
import dj_database_url
from .base import *

DEBUG = False

ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "*").split(",")

SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True

if os.environ.get("DATABASE_URL"):
    DATABASES = {
        "default": dj_database_url.parse(os.environ.get("DATABASE_URL"))
    }

if os.environ.get("REDIS_URL"):
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": os.environ.get("REDIS_URL"),
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
            },
        }
    }
    CELERY_BROKER_URL = os.environ.get("REDIS_URL")
    CELERY_RESULT_BACKEND = os.environ.get("REDIS_URL")